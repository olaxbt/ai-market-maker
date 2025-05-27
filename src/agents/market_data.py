import ccxt
import os
from typing import Dict, Optional
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class MarketDataAgent:
    def __init__(self, exchange: str, testnet: bool = False):
        self.exchange = getattr(ccxt, exchange)({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })
        if testnet:
            self.exchange.set_sandbox_mode(True)
        self.exchange.load_markets()

    def fetch_data(self, ticker: str, timeframe: str = "1h") -> Dict:
        try:
            ohlcv = self.exchange.fetch_ohlcv(ticker, timeframe, limit=20)
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
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            }
