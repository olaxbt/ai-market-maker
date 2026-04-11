"""Common technical indicators via TA-Lib (close-only and optional full OHLCV)."""

from __future__ import annotations

import logging

import numpy as np
import talib

logger = logging.getLogger(__name__)

# MACD(12,26,9) needs a longer history before values stabilize.
_MIN_BARS_CLOSE_EXTENDED = 40
# HLC indicators need a bit more than ``period`` for warm-up.
_MIN_BARS_HLC_FACTOR = 3


def _to_float_array(series: list[float] | None) -> np.ndarray | None:
    if not series:
        return None
    out = [
        float(x)
        for x in series
        if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x))
    ]
    if len(out) < 2:
        return None
    return np.asarray(out, dtype=np.float64)


def _last_scalar(a: np.ndarray | None, default: float = float("nan")) -> float:
    if a is None or len(a) == 0:
        return default
    x = float(a[-1])
    return x if not np.isnan(x) else default


def _empty_result(close_hint: float | None = None) -> dict[str, float]:
    """Neutral / NaN defaults when data is insufficient."""
    last = close_hint if close_hint is not None and not np.isnan(close_hint) else float("nan")
    return {
        "rsi": 50.0,
        "sma": last,
        "ema": last,
        "bb_upper": last,
        "bb_mid": last,
        "bb_lower": last,
        "macd": float("nan"),
        "macd_signal": float("nan"),
        "macd_hist": 0.0,
        "atr": float("nan"),
        "stoch_k": float("nan"),
        "stoch_d": float("nan"),
        "adx": float("nan"),
        "cci": float("nan"),
        "willr": float("nan"),
        "obv": float("nan"),
        "mfi": float("nan"),
        "roc": float("nan"),
    }


def calculate_technical_indicators(
    prices: list[float],
    period: int = 14,
    *,
    high: list[float] | None = None,
    low: list[float] | None = None,
    open_: list[float] | None = None,
    volume: list[float] | None = None,
) -> dict[str, float]:
    """
    Compute a bundle of widely used indicators.

    **Close-only** (``prices`` = closes): RSI, SMA, EMA, Bollinger Bands, MACD, ROC.

    **With ``high``, ``low``** (same length as ``prices``): also ATR, Stochastic,
    ADX, CCI, Williams %R.

    **With ``volume``** (same length): also OBV and MFI.

    ``open_`` is accepted for API symmetry; not required for this bundle.

    Returns the latest bar's values; uses RSI=50 and macd_hist=0 as soft neutrals
    when series are too short (see also NaNs for unavailable fields).
    """
    _ = open_  # reserved for future patterns (e.g. CDL*)

    if not prices or len(prices) < period + 1:
        logger.warning("Insufficient closes: %s (need at least %s)", len(prices or []), period + 1)
        return _empty_result()

    close = _to_float_array(prices)
    if close is None or len(close) < period + 1:
        logger.warning("Invalid or shortened close series after cleaning")
        return _empty_result()

    last_close = float(close[-1])
    h = _to_float_array(high)
    low_arr = _to_float_array(low)
    v = _to_float_array(volume)
    hlc_ok = (
        h is not None
        and low_arr is not None
        and len(h) == len(close)
        and len(low_arr) == len(close)
    )
    vol_ok = v is not None and len(v) == len(close)

    min_hlc = max(period * _MIN_BARS_HLC_FACTOR, period + 2)
    min_macd = _MIN_BARS_CLOSE_EXTENDED

    result: dict[str, float] = _empty_result(last_close)

    try:
        rsi = talib.RSI(close, timeperiod=period)
        sma = talib.SMA(close, timeperiod=period)
        ema = talib.EMA(close, timeperiod=period)
        bb_upper, bb_mid, bb_lower = talib.BBANDS(
            close, timeperiod=period, nbdevup=2, nbdevdn=2, matype=0
        )

        result["rsi"] = _last_scalar(rsi, 50.0)
        result["sma"] = _last_scalar(sma, last_close)
        result["ema"] = _last_scalar(ema, last_close)
        result["bb_upper"] = _last_scalar(bb_upper, last_close)
        result["bb_mid"] = _last_scalar(bb_mid, last_close)
        result["bb_lower"] = _last_scalar(bb_lower, last_close)

        if len(close) >= min_macd:
            macd, macd_signal, macd_hist = talib.MACD(
                close, fastperiod=12, slowperiod=26, signalperiod=9
            )
            result["macd"] = _last_scalar(macd)
            result["macd_signal"] = _last_scalar(macd_signal)
            mh = macd_hist[-1] if macd_hist is not None and len(macd_hist) else float("nan")
            result["macd_hist"] = float(mh) if not np.isnan(mh) else 0.0
        else:
            result["macd_hist"] = 0.0

        roc = talib.ROC(close, timeperiod=period)
        result["roc"] = _last_scalar(roc)

        if hlc_ok and len(close) >= min_hlc:
            atr = talib.ATR(h, low_arr, close, timeperiod=period)
            slowk, slowd = talib.STOCH(
                h,
                low_arr,
                close,
                fastk_period=5,
                slowk_period=3,
                slowk_matype=0,
                slowd_period=3,
                slowd_matype=0,
            )
            adx = talib.ADX(h, low_arr, close, timeperiod=period)
            cci = talib.CCI(h, low_arr, close, timeperiod=period)
            willr = talib.WILLR(h, low_arr, close, timeperiod=period)

            result["atr"] = _last_scalar(atr)
            result["stoch_k"] = _last_scalar(slowk)
            result["stoch_d"] = _last_scalar(slowd)
            result["adx"] = _last_scalar(adx)
            result["cci"] = _last_scalar(cci)
            result["willr"] = _last_scalar(willr)

        if hlc_ok and vol_ok and len(close) >= min_hlc:
            obv = talib.OBV(close, v)
            mfi = talib.MFI(h, low_arr, close, v, timeperiod=period)
            result["obv"] = _last_scalar(obv)
            result["mfi"] = _last_scalar(mfi)

        logger.debug(
            "TA snapshot: rsi=%s ema=%s macd_hist=%s adx=%s",
            result["rsi"],
            result["ema"],
            result["macd_hist"],
            result["adx"],
        )
        return result
    except Exception as e:
        logger.error("Indicator calculation error: %s", e)
        return _empty_result(last_close)


def indicator_keys() -> tuple[str, ...]:
    """Stable ordered keys returned by :func:`calculate_technical_indicators`."""
    return tuple(_empty_result().keys())


__all__ = ["calculate_technical_indicators", "indicator_keys"]
