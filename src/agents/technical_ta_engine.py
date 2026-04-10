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
            return {
                "status": "success",
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": clean,
                "indicator_catalog_version": "ta_bundle/v1",
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "ta_period": period,
                "bars": len(closes),
                "ta_indicators": {},
            }
