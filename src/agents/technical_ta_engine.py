"""Tier-0 Agent 2.3 — classical TA from OHLCV (TA-Lib bundle)."""

from __future__ import annotations

import math
import os
from typing import Any


def _extract_ohlcv_rows(market_data: dict[str, Any], ticker: str) -> list[list[Any]]:
    sym = market_data.get(ticker) if isinstance(market_data, dict) else None
    if not isinstance(sym, dict):
        return []
    raw = sym.get("ohlcv")
    return raw if isinstance(raw, list) else []


def _split_ohlcv(
    ohlcv: list[list[Any]],
) -> tuple[list[float], list[float], list[float], list[float], list[float]]:
    opens, highs, lows, closes, vols = [], [], [], [], []
    for row in ohlcv:
        if not isinstance(row, (list, tuple)) or len(row) < 6:
            continue
        try:
            opens.append(float(row[1]))
            highs.append(float(row[2]))
            lows.append(float(row[3]))
            closes.append(float(row[4]))
            vols.append(float(row[5]))
        except (TypeError, ValueError):
            continue
    return opens, highs, lows, closes, vols


def _sanitize_ta_floats(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            out[k] = None
        else:
            out[k] = v
    return out


def _enrich_ta_indicators(closes: list[float], ta: dict[str, Any]) -> dict[str, Any]:
    """Add desk-native trend/momentum fields to the TA bundle (no backtest fallback)."""
    out: dict[str, Any] = dict(ta)
    if len(closes) < 2:
        return out

    lookback = int(os.getenv("AIMM_TA_MOMENTUM_LOOKBACK") or "6")
    lookback = max(2, min(lookback, len(closes) - 1))
    c0 = closes[-lookback - 1]
    c1 = closes[-1]
    if c0 > 0:
        out["price_momentum"] = (c1 - c0) / c0

    ema_fast_p = int(os.getenv("AIMM_TA_EMA_FAST") or "9")
    ema_slow_p = int(os.getenv("AIMM_TA_EMA_SLOW") or "21")
    if len(closes) >= ema_slow_p + 1:
        try:
            import numpy as np
            import talib

            arr = np.asarray(closes, dtype=np.float64)
            ef = talib.EMA(arr, timeperiod=ema_fast_p)
            es = talib.EMA(arr, timeperiod=ema_slow_p)
            ef_v = float(ef[-1]) if ef is not None and len(ef) else None
            es_v = float(es[-1]) if es is not None and len(es) else None
            if ef_v is not None and es_v is not None and not (math.isnan(ef_v) or math.isnan(es_v)):
                out["ema"] = {"fast": ef_v, "slow": es_v}
        except Exception:
            pass

    sma = out.get("sma")
    if isinstance(sma, (int, float)) and float(sma) > 0 and c1 > 0:
        out["close_vs_sma"] = (c1 - float(sma)) / float(sma)

    return out


class TechnicalTaEngineAgent:
    """Computes the shared TA bundle; feeds Tier-0 agent ``2.3`` contract."""

    def analyze(self, *, ticker: str, market_data: dict[str, Any]) -> dict[str, Any]:
        if (os.getenv("AIMM_TA_TIER0_DISABLE") or "").strip().lower() in ("1", "true", "yes"):
            return {
                "status": "skipped",
                "reason": "AIMM_TA_TIER0_DISABLE",
                "ta_period": int(os.getenv("AIMM_TA_PERIOD") or "14"),
                "bars": 0,
                "ta_indicators": {},
            }

        period = int(os.getenv("AIMM_TA_PERIOD") or "14")
        ohlcv = _extract_ohlcv_rows(market_data, ticker)
        _, highs, lows, closes, vols = _split_ohlcv(ohlcv)
        if len(closes) < period + 1:
            return {
                "status": "skipped",
                "reason": "insufficient_bars",
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": {},
            }

        try:
            from tools.technical_indicators import calculate_technical_indicators
        except ImportError as e:
            return {
                "status": "error",
                "error": str(e),
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": {},
            }

        h_ok = len(highs) == len(closes) and len(lows) == len(closes)
        v_ok = len(vols) == len(closes)
        try:
            ta = calculate_technical_indicators(
                closes,
                period=period,
                high=highs if h_ok else None,
                low=lows if h_ok else None,
                volume=vols if v_ok else None,
            )
            clean = _sanitize_ta_floats(ta)
            enriched = _enrich_ta_indicators(closes, clean)
            return {
                "status": "success",
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": enriched,
                "indicator_catalog_version": "ta_bundle/v2",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": {},
            }
