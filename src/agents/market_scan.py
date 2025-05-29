from typing import Dict, List
from pycoingecko import CoinGeckoAPI
import ccxt
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class MarketScanAgent:
    def __init__(self, exchange: str = "binance", testnet: bool = False):
        self.exchange = getattr(ccxt, exchange)({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        try:
            self.exchange.load_markets()
        except Exception as e:
            logger.error(f"Failed to load markets: {str(e)}")
            raise
        self.cg = CoinGeckoAPI()

    def fetch_data(self, ticker: str, timeframe: str = "1h") -> Dict:
        """Fetch OHLCV and order book for a ticker."""
        if not ticker or not isinstance(ticker, str):
            logger.error("Invalid ticker provided")
            return {"ticker": ticker, "status": "error", "error": "Invalid ticker"}

        if ticker not in self.exchange.markets:
            logger.warning(f"Ticker {ticker} not found in exchange markets")
            return {"ticker": ticker, "status": "error", "error": f"Ticker {ticker} not available"}

        try:
            ohlcv = self.exchange.fetch_ohlcv(ticker, timeframe, limit=100)
            order_book = self.exchange.fetch_order_book(ticker, limit=5)
            logger.info(f"Fetched {len(ohlcv)} OHLCV candles for {ticker}")
            return {
                "ticker": ticker,
                "ohlcv": ohlcv,
                "bids": order_book["bids"],
                "asks": order_book["asks"],
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {str(e)}")
            return {"ticker": ticker, "status": "error", "error": str(e)}

    def scan_meme_coins(self) -> List[Dict]:
        """
            Scan for newly listed meme coins.
            Using CoinGecko
        """
        try:
            coins = self.cg.get_coins_markets(
                vs_currency="usd", category="meme-token", per_page=50)
            new_coins = []
            for coin in coins:
                categories = coin.get("categories", []) or []
                # Relaxed filtering to include any coin in meme-token category
                if coin.get("market_cap", 0) > 0:
                    new_coins.append({
                        "symbol": str(coin["symbol"]).upper() + "/USDT",
                        "name": coin["name"],
                        "price": coin["current_price"],
                        "volume": coin["total_volume"],
                        "market_cap": coin["market_cap"],
                        "listed_date": coin.get("last_updated", "")
                    })

            logger.info(f"Found {len(new_coins)} meme coins")
            return sorted(new_coins, key=lambda x: x["market_cap"], reverse=True)[:5]
        except Exception as e:
            logger.error(f"Error retrieving meme coins: {str(e)}")
            return []
