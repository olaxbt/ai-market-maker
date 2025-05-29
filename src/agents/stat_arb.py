from typing import Dict, List
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class StatArbAgent:
    def analyze(self, market_data: Dict, market_scan: List) -> Dict:
        try:
            results = {}
            # Require at least two tickers for arbitrage
            tickers = [ticker for ticker in market_data if market_data[ticker].get(
                "status") == "success"]
            if len(tickers) < 2:
                logger.warning(
                    f"Insufficient tickers for arbitrage: {tickers}")
                return {"status": "error", "analysis": "Need at least two tickers"}

            # Simple pair trading example
            for i, ticker1 in enumerate(tickers):
                for ticker2 in tickers[i+1:]:
                    data1 = market_data[ticker1]
                    data2 = market_data[ticker2]
                    if not (data1.get("ohlcv") and data2.get("ohlcv")):
                        logger.warning(
                            f"Missing OHLCV for {ticker1} or {ticker2}")
                        continue
                    closes1 = [candle[4] for candle in data1["ohlcv"]]
                    closes2 = [candle[4] for candle in data2["ohlcv"]]
                    if len(closes1) < 20 or len(closes2) < 20:
                        logger.warning(
                            f"Insufficient OHLCV data for {ticker1}/{ticker2}")
                        continue
                    spread = np.array(closes1[-20:]) - np.array(closes2[-20:])
                    mean_spread = np.mean(spread)
                    std_spread = np.std(spread)
                    current_spread = closes1[-1] - closes2[-1]
                    z_score = (current_spread - mean_spread) / \
                        (std_spread + 1e-6)
                    results[f"{ticker1}-{ticker2}"] = {
                        "z_score": z_score,
                        "signal": "buy" if z_score < -2 else "sell" if z_score > 2 else "hold"
                    }
            if not results:
                logger.warning("No valid arbitrage pairs found")
                return {"status": "error", "analysis": "No valid pairs"}
            logger.info(f"Arbitrage results: {results}")
            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Stat arb error: {str(e)}")
            return {"status": "error", "analysis": str(e)}
