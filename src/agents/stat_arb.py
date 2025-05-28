from typing import Dict
from tools.api import fetch_order_book
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class StatArbAgent:
    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange

    def analyze(self, ticker1: str, ticker2: str) -> Dict:
        try:
            book1 = fetch_order_book(
                ticker1, self.exchange, testnet=os.getenv("BINANCE_API_KEY") is not None)
            book2 = fetch_order_book(
                ticker2, self.exchange, testnet=os.getenv("BINANCE_API_KEY") is not None)

            if not book1.get("bids") or not book2.get("asks"):
                return {
                    "tickers": [ticker1, ticker2],
                    "status": "error",
                    "error": "Invalid order book data"
                }

            btc_bid = book1["bids"][0][0]
            eth_ask = book2["asks"][0][0]
            btc_eth_ratio = btc_bid / eth_ask

            if btc_eth_ratio > 1.05:
                signal = f"Buy {ticker2}, sell {ticker1}"
            elif btc_eth_ratio < 0.95:
                signal = f"Buy {ticker1}, sell {ticker2}"
            else:
                signal = "No arbitrage opportunity"

            logger.info(f"Arbitrage signal: {signal}")
            return {
                "tickers": [ticker1, ticker2],
                "ratio": btc_eth_ratio,
                "signal": signal,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"StatArb error for {ticker1}, {ticker2}: {str(e)}")
            return {
                "tickers": [ticker1, ticker2],
                "status": "error",
                "error": str(e)
            }
