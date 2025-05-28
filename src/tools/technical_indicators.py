from typing import Dict, List
import pandas as pd
import numpy as np
import talib
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def calculate_technical_indicators(prices: List[float], period: int = 14) -> Dict:
    """
    Calculate RSI, SMA, and Bollinger Bands using TA-Lib.
    Returns a dict with the latest values or defaults if insufficient data.
    """
    try:
        if not prices or len(prices) < period + 1:
            logger.warning(
                f"Insufficient data: {len(prices)} prices, need {period + 1}")
            return {
                "rsi": 50.0,
                "sma": np.nan,
                "bb_upper": np.nan,
                "bb_lower": np.nan,
                "bb_mid": np.nan
            }

        # Validate prices
        prices = np.array([float(p) for p in prices if isinstance(
            p, (int, float)) and not np.isnan(p)])
        if len(prices) < period + 1:
            logger.warning(
                f"Valid prices reduced to {len(prices)}, need {period + 1}")
            return {
                "rsi": 50.0,
                "sma": np.nan,
                "bb_upper": np.nan,
                "bb_lower": np.nan,
                "bb_mid": np.nan
            }

        # Calculate indicators
        rsi = talib.RSI(prices, timeperiod=period)
        sma = talib.SMA(prices, timeperiod=period)
        bb_upper, bb_mid, bb_lower = talib.BBANDS(
            prices, timeperiod=period, nbdevup=2, nbdevdn=2, matype=0)

        # Get latest values, handle NaN
        result = {
            # Default RSI=50
            "rsi": rsi[-1] if not np.isnan(rsi[-1]) else 50.0,
            "sma": sma[-1] if not np.isnan(sma[-1]) else prices[-1],
            "bb_upper": bb_upper[-1] if not np.isnan(bb_upper[-1]) else prices[-1],
            "bb_lower": bb_lower[-1] if not np.isnan(bb_lower[-1]) else prices[-1],
            "bb_mid": bb_mid[-1] if not np.isnan(bb_mid[-1]) else prices[-1]
        }

        logger.debug(f"Indicators: RSI={result['rsi']:.2f}, SMA={result['sma']:.2f}, "
                     f"BB_Upper={result['bb_upper']:.2f}, BB_Lower={result['bb_lower']:.2f}")
        return result
    except Exception as e:
        logger.error(f"Indicator calculation error: {str(e)}")
        return {
            "rsi": 50.0,
            "sma": prices[-1] if prices.size else np.nan,
            "bb_upper": prices[-1] if prices.size else np.nan,
            "bb_lower": prices[-1] if prices.size else np.nan,
            "bb_mid": prices[-1] if prices.size else np.nan
        }
