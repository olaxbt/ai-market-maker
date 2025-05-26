from typing import List
import pandas as pd
import numpy as np


def calculate_rsi(prices: List[float], period: int = 14) -> List[float]:
    try:
        if len(prices) < period + 1:
            return [np.nan] * len(prices)

        series = pd.Series(prices)
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
        rs = gain / loss
        # Handle division by zero and infinity
        rs = rs.fillna(0).replace(np.inf, 0)
        rsi = 100 - (100 / (1 + rs))
        return rsi.tolist()
    except Exception as e:
        raise Exception(f"RSI calculation error: {str(e)}")
