"""OHLCV-derived Nexus-shaped context for deterministic backtests.

Backtest ``market_scan`` skips live Nexus fetches. This module synthesizes a
minimal ``shared_memory["nexus"]`` bundle from the same OHLCV window so Tier-0
agents (1.1 macro, 2.1 pattern) receive richer inputs without look-ahead or
live API calls.

Nexus-heavy desks (news, sentiment, whale flow) still need recorded fixtures or
a historical Nexus API — out of scope here; see ``docs/backtest-data.md``.
"""

from __future__ import annotations

import time
from typing import Any


def _closes(ohlcv: list) -> list[float]:
    out: list[float] = []
    for row in ohlcv:
        if isinstance(row, (list, tuple)) and len(row) > 4:
            try:
                c = float(row[4])
                if c > 0:
                    out.append(c)
            except (TypeError, ValueError):
                pass
    return out


def _return_vol(closes: list[float], *, lookback: int = 30) -> tuple[float, float]:
    """Window return % and annualized vol % from daily closes."""
    if len(closes) < 2:
        return 0.0, 0.0
    seg = closes[-min(lookback, len(closes)) :]
    if len(seg) < 2 or seg[0] <= 0:
        return 0.0, 0.0
    ret_pct = (seg[-1] / seg[0] - 1.0) * 100.0
    rets: list[float] = []
    for i in range(1, len(seg)):
        if seg[i - 1] > 0:
            rets.append((seg[i] / seg[i - 1] - 1.0) * 100.0)
    vol = (sum(r * r for r in rets) / len(rets)) ** 0.5 * (365**0.5) if rets else 0.0
    return ret_pct, vol


def _liquidity_score(ret_pct: float, vol_pct: float) -> tuple[float, bool, bool]:
    """Map trend/vol to systemic liquidity score and risk flags."""
    score = 50.0 + ret_pct * 0.8 - min(vol_pct, 80.0) * 0.15
    score = max(10.0, min(95.0, score))
    risk_on = ret_pct > 2.0 and vol_pct < 60.0
    risk_off = ret_pct < -5.0 or vol_pct > 90.0
    if risk_off:
        score = max(10.0, score - 12.0)
    elif risk_on:
        score = min(95.0, score + 8.0)
    return score, risk_on, risk_off


def _symbol_ta_from_ohlcv(ohlcv: list) -> dict[str, Any]:
    closes = _closes(ohlcv)
    n = len(closes)
    if n < 5:
        return {"ok": False, "error": "insufficient_bars", "data": None}
    seg = closes[-min(20, n) :]
    lo, hi = min(seg), max(seg)
    last = seg[-1]
    ret_5 = (seg[-1] / seg[0] - 1.0) * 100.0 if seg[0] > 0 else 0.0
    trend = "bullish" if ret_5 > 1.5 else "bearish" if ret_5 < -1.5 else "neutral"
    return {
        "ok": True,
        "data": {
            "success": True,
            "trend": trend,
            "support": round(lo, 2),
            "resistance": round(hi, 2),
            "last_price": round(last, 2),
            "return_window_pct": round(ret_5, 4),
            "pattern_hint": "range"
            if abs(ret_5) < 2.0
            else ("uptrend" if ret_5 > 0 else "downtrend"),
            "source": "ohlcv_derived",
        },
    }


def build_ohlcv_derived_nexus_context(
    *,
    ticker: str,
    universe: list[str],
    market_data: dict[str, Any],
) -> dict[str, Any]:
    """Build a Nexus-shaped bundle from completed OHLCV only (no look-ahead)."""
    primary = str(ticker or "BTC/USDT")
    md = market_data if isinstance(market_data, dict) else {}
    primary_blob = md.get(primary) or {}
    primary_ohlcv = primary_blob.get("ohlcv") if isinstance(primary_blob, dict) else []
    closes = _closes(primary_ohlcv if isinstance(primary_ohlcv, list) else [])
    ret_pct, vol_pct = _return_vol(closes)
    liq_score, risk_on, risk_off = _liquidity_score(ret_pct, vol_pct)

    per_by_symbol: dict[str, Any] = {}
    for sym in universe:
        if not isinstance(sym, str):
            continue
        blob = md.get(sym) or {}
        ohlcv = blob.get("ohlcv") if isinstance(blob, dict) else []
        if not isinstance(ohlcv, list):
            continue
        per_by_symbol[sym] = {
            "coin": {"ok": True, "data": {"symbol": sym, "source": "ohlcv_derived"}},
            "technical_analysis": _symbol_ta_from_ohlcv(ohlcv),
            "quant_summary": {"ok": False, "error": "ohlcv_derived_stub", "data": None},
        }

    return {
        "fetched_at_epoch": time.time(),
        "integration_contract_version": "ohlcv-derived/v1",
        "source": "ohlcv_derived",
        "endpoints": {
            "market_overview": {
                "ok": True,
                "data": {
                    "success": True,
                    "systemic_liquidity_score": round(liq_score, 2),
                    "liquidity_score": round(liq_score, 2),
                    "risk_on": risk_on,
                    "risk_off": risk_off,
                    "window_return_pct": round(ret_pct, 4),
                    "window_vol_annualized_pct": round(vol_pct, 4),
                    "primary_symbol": primary,
                },
            },
        },
        "per_symbol": {"by_symbol": per_by_symbol},
        "errors": [],
    }


def backtest_ohlcv_nexus_enabled() -> bool:
    import os

    raw = (os.environ.get("AIMM_BACKTEST_OHLCV_NEXUS") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


__all__ = [
    "backtest_ohlcv_nexus_enabled",
    "build_ohlcv_derived_nexus_context",
]
