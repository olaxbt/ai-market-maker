import ccxt
import os
from typing import Dict, Optional
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, filename="trades.log",
                    format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class OrderPlacementAgent:
    def __init__(self, exchange: str, testnet: bool = False):
        self.exchange = getattr(ccxt, exchange)({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self.testnet = testnet
        self.positions = {}

    def place_order(self, ticker: str, market_data: Dict, spread: float = 0.005, quantity: float = 0.001) -> Dict:
        try:
            best_bid = market_data["bids"][0][0] if market_data["bids"] else None
            best_ask = market_data["asks"][0][0] if market_data["asks"] else None
            if not best_bid or not best_ask:
                return {"ticker": ticker, "status": "error", "error": "Invalid market data"}

            mid_price = (best_bid + best_ask) / 2
            bid = mid_price * (1 - spread / 2)

            if self.testnet and os.getenv("BINANCE_API_KEY") and os.getenv("BINANCE_API_SECRET"):
                order = self.exchange.create_limit_buy_order(
                    ticker, quantity, bid)
                trade = {
                    "ticker": ticker,
                    "type": "buy",
                    "price": bid,
                    "quantity": quantity,
                    "order_id": order["id"],
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "success",
                    "message": f"Testnet buy order placed: {quantity} {ticker} at {bid}"
                }
            else:
                trade = {
                    "ticker": ticker,
                    "type": "buy",
                    "price": bid,
                    "quantity": quantity,
                    "timestamp": datetime.utcnow().isoformat(),
                    "status": "success",
                    "message": f"Simulated buy: {quantity} {ticker} at {bid}"
                }

            if ticker not in self.positions:
                self.positions[ticker] = {"quantity": 0, "avg_price": 0}
            current = self.positions[ticker]
            new_quantity = current["quantity"] + quantity
            new_avg_price = ((current["quantity"] * current["avg_price"]) +
                             (quantity * bid)) / new_quantity if new_quantity else 0
            self.positions[ticker] = {
                "quantity": new_quantity, "avg_price": new_avg_price}

            logger.info(
                f"Trade: {trade['message']}, Position: {self.positions[ticker]}")

            return {
                **trade,
                "bid": bid,
                "ask": mid_price * (1 + spread / 2),
                "mid_price": mid_price,
                "position": self.positions[ticker]
            }
        except Exception as e:
            logger.error(f"Error placing order for {ticker}: {str(e)}")
            return {"ticker": ticker, "status": "error", "error": str(e)}
