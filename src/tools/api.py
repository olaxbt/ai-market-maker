import ccxt
from typing import Dict, List


def fetch_ohlcv(ticker: str, exchange: str = "binance", timeframe: str = "1h", limit: int = 10) -> List:
    exchange = getattr(ccxt, exchange)()
    exchange.load_markets()
    return exchange.fetch_ohlcv(ticker, timeframe, limit)


def fetch_order_book(ticker: str, exchange: str = "binance", limit: int = 5) -> Dict:
    exchange = getattr(ccxt, exchange)()
    exchange.load_markets()
    return exchange.fetch_order_book(ticker, limit)
