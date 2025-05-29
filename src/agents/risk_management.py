import logging
from typing import Dict
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class RiskManagementAgent:
    def analyze(self, market_data: Dict, valuation: Dict) -> Dict:
        try:
            results = {}
            for ticker in market_data:
                if market_data[ticker].get("status") != "success":
                    continue
                ohlcv = market_data[ticker]["ohlcv"]
                if len(ohlcv) < 20:
                    logger.warning(f"Insufficient OHLCV data for {ticker}")
                    continue
                # Calculate volatility using recent 20 candles
                closes = [candle[4] for candle in ohlcv[-20:]]
                volatility = np.std(closes) / np.mean(closes)
                current_price = closes[-1]
                # Use valuation to adjust position size
                val = valuation.get(ticker, {}).get("value", current_price)
                risk_multiplier = 1.0 if val >= current_price else 0.5
                # Position size: Cap at $1000, adjust based on volatility and valuation
                position_size = min(
                    1000, 1000 / (1 + volatility)) * risk_multiplier
                # Stop-loss: 5% below current price
                stop_price = current_price * 0.95
                results[ticker] = {
                    "position_size": position_size,
                    "stop_price": stop_price,
                    "volatility": volatility
                }
            logger.info(f"Risk analysis: {results}")
            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Risk analysis error: {str(e)}")
            return {"status": "error", "message": str(e)}
