from typing import Dict, List
import numpy as np
import talib
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class QuantAgent:
    def analyze(self, market_data: Dict) -> Dict:
        try:
            results = {}
            for ticker, data in market_data.items():
                if not data.get("ohlcv"):
                    continue
                closes = np.array([candle[4] for candle in data["ohlcv"]])
                volumes = np.array([candle[5] for candle in data["ohlcv"]])

                # MACD
                macd, signal, _ = talib.MACD(
                    closes, fastperiod=12, slowperiod=26, signalperiod=9)
                macd_signal = "buy" if macd[-1] > signal[-1] and macd[-2] <= signal[-2] else "sell" if macd[-1] < signal[-1] else "hold"

                # Volume spike
                vol_spike = "spike" if volumes[-1] > np.mean(
                    volumes[-10:]) * 1.5 else "normal"

                results[ticker] = {
                    "macd_signal": macd_signal, "volume": vol_spike}
                logger.info(
                    f"Quant {ticker}: MACD={macd_signal}, Volume={vol_spike}")

            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Quant error: {str(e)}")
            return {"status": "error", "analysis": str(e)}
