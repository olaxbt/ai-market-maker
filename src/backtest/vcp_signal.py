"""VCP pattern signal adapter for alt symbols in backtests."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

from backtest.exchange_trade_format import ccxt_symbol_to_binance

_SCREENER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "token_screeners"
_detect_vcp = None
_DEFAULT_PARAMS: dict[str, Any] | None = None


def _load_vcp_scanner():
    global _detect_vcp, _DEFAULT_PARAMS
    if _detect_vcp is not None:
        return _detect_vcp, _DEFAULT_PARAMS or {}
    screener = str(_SCREENER_DIR)
    if screener not in sys.path:
        sys.path.insert(0, screener)
    from vcp_scanner import DEFAULT_PARAMS, detect_vcp

    _detect_vcp = detect_vcp
    _DEFAULT_PARAMS = dict(DEFAULT_PARAMS)
    return _detect_vcp, _DEFAULT_PARAMS


def timeframe_to_scan_tf(timeframe: str, interval_sec: int = 0) -> str:
    tf = (timeframe or "").strip().lower()
    if tf in ("1d", "1day", "d"):
        return "1d"
    if tf in ("4h",):
        return "4h"
    if tf in ("1h",):
        return "1h"
    if tf in ("15m",):
        return "15m"
    if interval_sec >= 86_400:
        return "1d"
    if interval_sec >= 14_400:
        return "4h"
    if interval_sec >= 3_600:
        return "1h"
    return "1h"


def bars_window_to_df(window: list[list[float]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for bar in window:
        if not bar or len(bar) < 6:
            continue
        ts = float(bar[0])
        if ts > 1e12:
            ts = ts / 1000.0
        rows.append(
            {
                "timestamp": pd.to_datetime(ts, unit="s", utc=True),
                "open": float(bar[1]),
                "high": float(bar[2]),
                "low": float(bar[3]),
                "close": float(bar[4]),
                "volume": float(bar[5]),
            }
        )
    return pd.DataFrame(rows)


def vcp_result_to_target_weight(res: Any) -> float:
    if getattr(res, "error", None):
        return 0.0
    if not getattr(res, "passed_relaxed", False):
        return 0.0
    conf = min(1.0, float(getattr(res, "vcp_score", 0.0)) / 100.0)
    dist = float(getattr(res, "distance_to_pivot_pct", 999.0))
    if dist > 5.0:
        return 0.0
    if getattr(res, "passed_strict", False):
        return conf
    return conf * 0.5


def vcp_target_weight_from_window(
    symbol: str,
    window: list[list[float]],
    *,
    btc_window: list[list[float]] | None = None,
    timeframe: str = "",
    interval_sec: int = 0,
    params: dict[str, Any] | None = None,
) -> tuple[float, dict[str, Any]]:
    """Return (target_weight, metadata) from completed OHLCV window."""
    detect_vcp, default_params = _load_vcp_scanner()
    scan_tf = timeframe_to_scan_tf(timeframe, interval_sec)
    merged = {**default_params, **(params or {}), "scan_tf": scan_tf}

    df = bars_window_to_df(window)
    if df.empty:
        return 0.0, {"strategy": "vcp", "error": "empty_window"}

    btc_df = None
    if btc_window:
        btc_df = bars_window_to_df(btc_window)
        if btc_df.empty:
            btc_df = None

    res = detect_vcp(
        df,
        symbol=ccxt_symbol_to_binance(symbol),
        params=merged,
        btc_df=btc_df,
    )
    weight = vcp_result_to_target_weight(res)
    meta: dict[str, Any] = {
        "strategy": "vcp",
        "vcp_score": res.vcp_score,
        "passed_strict": res.passed_strict,
        "passed_relaxed": res.passed_relaxed,
        "distance_to_pivot_pct": res.distance_to_pivot_pct,
        "scan_tf": res.scan_tf,
        "bar_count": res.bar_count,
    }
    if res.error:
        meta["error"] = res.error
    action = "BUY" if weight > 1e-9 else "HOLD"
    meta["decision"] = {
        "action": action,
        "confidence": abs(weight),
        "stance": "bullish" if weight > 0 else "neutral",
    }
    return weight, meta


__all__ = [
    "bars_window_to_df",
    "timeframe_to_scan_tf",
    "vcp_result_to_target_weight",
    "vcp_target_weight_from_window",
]
