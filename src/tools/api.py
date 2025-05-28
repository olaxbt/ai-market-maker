import ccxt
import os
from typing import Dict, List

_cache = {}


def fetch_ohlcv(ticker: str, exchange: str = "binance", timeframe: str = "1h", limit: int = 20, testnet: bool = False) -> List:
    cache_key = f"ohlcv_{ticker}_{timeframe}"
    if cache_key in _cache:
        return _cache[cache_key]
    exchange = getattr(ccxt, exchange)({
        "apiKey": os.getenv("BINANCE_API_KEY"),
        "secret": os.getenv("BINANCE_API_SECRET"),
        "enableRateLimit": True
    })
    if testnet:
        exchange.set_sandbox_mode(True)
    exchange.load_markets()
    data = exchange.fetch_ohlcv(ticker, timeframe, limit)
    _cache[cache_key] = data
    return data


def fetch_order_book(ticker: str, exchange: str = "binance", limit: int = 5, testnet: bool = False) -> Dict:
    cache_key = f"order_book_{ticker}"
    if cache_key in _cache:
        return _cache[cache_key]
    exchange = getattr(ccxt, exchange)({
        "apiKey": os.getenv("BINANCE_API_KEY"),
        "secret": os.getenv("BINANCE_API_SECRET"),
        "enableRateLimit": True
    })
    if testnet:
        exchange.set_sandbox_mode(True)
    exchange.load_markets()
    data = exchange.fetch_order_book(ticker, limit)
    _cache[cache_key] = data
    return data
