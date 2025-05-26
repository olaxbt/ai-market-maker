import ccxt
from typing import Dict, Optional


class MarketDataAgent:
    def __init__(self, exchange: str):
        self.exchange = getattr(ccxt, exchange)()
        self.exchange.load_markets()

    def fetch_data(self, ticker: str, timeframe: str = "1h") -> Dict:
        try:
            ohlcv = self.exchange.fetch_ohlcv(ticker, timeframe, limit=30)
            order_book = self.exchange.fetch_order_book(
                ticker, limit=5)  # Get Top 5 bids, asks

            return {
                "ticker": ticker,
                "ohlcv": ohlcv,
                "bids": order_book["bids"],
                "asks": order_book["asks"],
                "status": "success"
            }
        except Exception as e:
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            }
