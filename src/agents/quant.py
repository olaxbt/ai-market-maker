import logging
from typing import Dict

import numpy as np
import talib

from strategies.presets import quant_trace_meta

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

                # MACD: trend (MACD vs signal), not only crossover (rare on short paths).
                macd, signal, _ = talib.MACD(closes, fastperiod=12, slowperiod=26, signalperiod=9)
                m0, s0 = float(macd[-1]), float(signal[-1])
                m1, s1 = float(macd[-2]), float(signal[-2])
                if not (np.isfinite(m0) and np.isfinite(s0)):
                    macd_signal = "hold"
                elif m0 > s0 and m1 <= s1:
                    macd_signal = "buy"  # bullish crossover
                elif m0 > s0:
                    macd_signal = "buy"  # bullish regime (common case for simulated paths)
                elif m0 < s0:
                    macd_signal = "sell"
                else:
                    macd_signal = "hold"

                # Volume spike (short windows when few bars)
                win = min(10, len(volumes))
                vol_spike = (
                    "spike"
                    if win >= 2 and volumes[-1] > np.mean(volumes[-win:]) * 1.5
                    else "normal"
                )

                results[ticker] = {"macd_signal": macd_signal, "volume": vol_spike}
                logger.info(f"Quant {ticker}: MACD={macd_signal}, Volume={vol_spike}")

            return {
                "status": "success",
                "analysis": results,
                "strategy": quant_trace_meta(),
            }
        except Exception as e:
            logger.error(f"Quant error: {str(e)}")
            return {"status": "error", "analysis": str(e), "strategy": quant_trace_meta()}
