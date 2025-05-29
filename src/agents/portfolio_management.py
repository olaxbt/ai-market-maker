import logging
from typing import Dict
import ccxt
import os
import json

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class PortfolioManagementAgent:
    def __init__(self, exchange: str = "binance", testnet: bool = False):
        self.exchange = getattr(ccxt, exchange)({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()
        self.positions_file = "positions.json"
        self.load_positions()

    def load_positions(self):
        """Load current positions from file."""
        try:
            if os.path.exists(self.positions_file):
                with open(self.positions_file, "r") as f:
                    # {ticker: {quantity, entry_price, timestamp}}
                    self.positions = json.load(f)
            else:
                self.positions = {}
        except Exception as e:
            logger.error(f"Error loading positions: {str(e)}")
            self.positions = {}

    def save_positions(self):
        """Save current positions to file."""
        try:
            with open(self.positions_file, "w") as f:
                json.dump(self.positions, f)
        except Exception as e:
            logger.error(f"Error saving positions: {str(e)}")

    def analyze(self, ticker: str, market_data: Dict, pattern_analysis: Dict, sentiment_analysis: Dict,
                arb_analysis: Dict, quant_analysis: Dict, valuation: Dict, risk: Dict,
                liquidity: Dict) -> Dict:
        try:
            # Step 1: Compute portfolio allocations
            allocations = {}
            total_budget = 5000  # Total USD budget
            risk_analysis = risk.get("analysis", {})
            tickers = [t for t in market_data if market_data[t].get(
                "status") == "success"]
            if not tickers:
                logger.warning("No valid market data for portfolio allocation")
                return {"status": "error", "message": "No valid market data"}

            # Allocate based on risk-adjusted position sizes
            total_position_size = sum(risk_analysis.get(
                t, {}).get("position_size", 0) for t in tickers)
            if total_position_size == 0:
                logger.warning("No position sizes available for allocation")
                return {"status": "error", "message": "No position sizes"}

            for t in tickers:
                position_size = risk_analysis.get(
                    t, {}).get("position_size", 0)
                weight = position_size / total_position_size if total_position_size > 0 else 0
                amount = weight * total_budget
                allocations[t] = {
                    "weight": weight,
                    "amount": amount,  # USD amount to allocate
                    "stop_price": risk_analysis.get(t, {}).get("stop_price", 0)
                }

            # Step 2: Place orders for the input ticker
            trades = {}
            if ticker not in self.exchange.markets:
                logger.error(f"Ticker {ticker} not available on exchange")
                trades[ticker] = {"status": "error",
                                  "message": f"Ticker {ticker} not available"}
            else:
                # Extract signals and portfolio allocations
                sentiment_score = sentiment_analysis.get("score", 50.0)
                arb_signal = arb_analysis.get("analysis", {}).get(
                    f"{ticker}-*", {}).get("signal", "hold")
                quant_signal = quant_analysis.get("signal", "hold")
                portfolio_alloc = allocations.get(ticker, {})
                target_amount = portfolio_alloc.get(
                    "amount", 0)  # USD amount to allocate
                stop_price = portfolio_alloc.get("stop_price", 0)
                # Latest closing price
                current_price = market_data[ticker]["ohlcv"][-1][4]

                # Check current position
                position = self.positions.get(ticker, None)
                has_position = position is not None
                trade_result = {"status": "skipped",
                                "message": "No trade signal"}

                # Calculate target quantity based on portfolio allocation
                target_quantity = target_amount / current_price if current_price > 0 else 0
                current_quantity = position["quantity"] if has_position else 0

                # Buy logic: Increase position to match target allocation
                if target_quantity > current_quantity:
                    if (sentiment_score > 75 and quant_signal == "buy") or arb_signal == "buy":
                        quantity_to_buy = target_quantity - current_quantity
                        order = self.exchange.create_market_buy_order(
                            ticker, quantity_to_buy)
                        if has_position:
                            # Update position
                            self.positions[ticker]["quantity"] += quantity_to_buy
                            self.positions[ticker]["entry_price"] = (
                                (position["entry_price"] * current_quantity + order["price"] * quantity_to_buy) /
                                (current_quantity + quantity_to_buy)
                            )
                            self.positions[ticker]["timestamp"] = order["datetime"]
                        else:
                            self.positions[ticker] = {
                                "quantity": quantity_to_buy,
                                "entry_price": order["price"],
                                "timestamp": order["datetime"]
                            }
                        self.save_positions()
                        logger.info(f"Placed buy order for {ticker}: {order}")
                        with open("trades.log", "a") as f:
                            f.write(
                                f"{ticker},buy,{quantity_to_buy},{order['price']},{order['datetime']}\n")
                        trade_result = {
                            "status": "success",
                            "order": order,
                            "position": self.positions[ticker],
                            "profit_loss": 0.0
                        }

                # Sell logic: Reduce position if below target or signals are negative
                elif has_position:
                    entry_price = position["entry_price"]
                    quantity = position["quantity"]
                    should_sell = (
                        (target_quantity < current_quantity) or
                        (sentiment_score < 25 or quant_signal == "sell" or arb_signal == "sell") or
                        (stop_price > 0 and current_price <= stop_price)
                    )
                    if should_sell:
                        quantity_to_sell = min(
                            current_quantity - target_quantity, current_quantity) if target_quantity < current_quantity else current_quantity
                        if quantity_to_sell > 0:
                            order = self.exchange.create_market_sell_order(
                                ticker, quantity_to_sell)
                            profit_loss = (
                                order["price"] - entry_price) * quantity_to_sell
                            remaining_quantity = current_quantity - quantity_to_sell
                            if remaining_quantity <= 0:
                                del self.positions[ticker]
                            else:
                                self.positions[ticker]["quantity"] = remaining_quantity
                            self.save_positions()
                            logger.info(
                                f"Placed sell order for {ticker}: {order}, Profit/Loss: {profit_loss}")
                            with open("trades.log", "a") as f:
                                f.write(
                                    f"{ticker},sell,{quantity_to_sell},{order['price']},{order['datetime']},{profit_loss}\n")
                            trade_result = {
                                "status": "success",
                                "order": order,
                                "position": self.positions.get(ticker, None),
                                "profit_loss": profit_loss
                            }
                    else:
                        current_value = current_price * current_quantity
                        entry_value = entry_price * current_quantity
                        profit_loss = current_value - entry_value
                        trade_result = {
                            "status": "hold",
                            "message": "Holding position",
                            "position": position,
                            "profit_loss": profit_loss
                        }

                trades[ticker] = trade_result

            # Step 3: Return allocations and trades
            result = {
                "status": "success",
                "allocations": allocations,
                "trades": trades
            }
            logger.info(f"Portfolio result: {result}")
            return result

        except Exception as e:
            logger.error(f"Portfolio analysis error: {str(e)}")
            return {"status": "error", "message": str(e)}
