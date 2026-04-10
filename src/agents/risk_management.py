import logging
import os
from typing import Dict

import numpy as np

from config.fund_policy import load_fund_policy

logger = logging.getLogger(__name__)


class RiskManagementAgent:
    def analyze(self, market_data: Dict, valuation: Dict) -> Dict:
        try:
            results = {}
            fp = load_fund_policy()
            cap = float(fp.risk_position_cap_usd)
            for ticker in market_data:
                st = market_data[ticker].get("status")
                if st not in ("success", "backtest"):
                    continue
                ohlcv = market_data[ticker].get("ohlcv") or []
                if len(ohlcv) < 1:
                    logger.warning("Insufficient OHLCV data for %s", ticker)
                    continue
                # Up to 20 candles so sizing works early in a backtest (bar 0 has only 1 row).
                tail = min(20, len(ohlcv))
                closes = [float(candle[4]) for candle in ohlcv[-tail:]]
                m = float(np.mean(closes)) if closes else 0.0
                if m <= 0:
                    logger.warning("Invalid close prices for %s", ticker)
                    continue
                if len(closes) >= 2:
                    volatility = float(np.std(closes) / m)
                else:
                    volatility = 0.02
                current_price = closes[-1]
                # Use valuation to adjust position size
                val = float(valuation.get(ticker, {}).get("value", current_price) or current_price)
                risk_multiplier = 1.0 if val >= current_price else 0.5
                # Position size: cap at ``AIMM_RISK_POSITION_CAP_USD``, volatility-scaled.
                position_size = float(min(cap, cap / (1.0 + volatility)) * risk_multiplier)
                stop_loss_pct = fp.stop_loss_pct
                stop_price = current_price * (1.0 - stop_loss_pct)
                results[ticker] = {
                    "position_size": position_size,
                    "stop_price": float(stop_price),
                    "stop_loss_pct": stop_loss_pct,
                    "volatility": volatility,
                }
            if (os.getenv("AIMM_DEBUG_RISK") or "").strip().lower() in ("1", "true", "yes", "on"):
                logger.info(
                    "Risk analysis sample (n=%s): %s", len(results), dict(list(results.items())[:3])
                )
            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Risk analysis error: {str(e)}")
            return {"status": "error", "message": str(e)}
