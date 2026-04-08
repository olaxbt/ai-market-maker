"""Resolve ``metric_id`` / Tier-0 contract fields for Tier-1 blueprint rules."""

from __future__ import annotations

from typing import Any


def _norm_symbol(ticker: str) -> str:
    return str(ticker or "").replace("/", "").replace("-", "").upper()


def tier0_by_agent_for_ticker(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Index Tier-0 rows by agent id, preferring rows whose ``ticker`` matches ``state['ticker']``."""
    want = _norm_symbol(str(state.get("ticker") or ""))
    per_agent: dict[str, list[dict[str, Any]]] = {}
    for row in state.get("tier0_contracts") or []:
        if not isinstance(row, dict) or not row.get("agent"):
            continue
        ag = str(row["agent"])
        per_agent.setdefault(ag, []).append(row)

    out: dict[str, dict[str, Any]] = {}
    for ag, rows in per_agent.items():
        if not rows:
            continue
        if want:
            for r in reversed(rows):
                if _norm_symbol(str(r.get("ticker") or "")) == want:
                    out[ag] = r
                    break
            else:
                out[ag] = rows[-1]
        else:
            out[ag] = rows[-1]
    return out


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _i(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return default


def _circuit_breaker_status(c12: dict[str, Any]) -> str:
    ni = _i(c12.get("News_Impact_Score"), 0)
    et = str(c12.get("Event_Type") or "")
    if ni >= 80 or "Black Swan" in et:
        return "TRIGGERED - AGGRESSIVE OVERRIDE"
    return "NORMAL"


def resolve_metric(metric_id: str, state: dict[str, Any]) -> Any:
    """Return a scalar (or comparable) for ``metric_id`` from Tier-0 contracts."""
    mid = (metric_id or "").strip().lower()
    idx = tier0_by_agent_for_ticker(state)

    c11 = idx.get("1.1") or {}
    c12 = idx.get("1.2") or {}
    c21 = idx.get("2.1") or {}
    c22 = idx.get("2.2") or {}
    c23 = idx.get("2.3") or {}
    c31 = idx.get("3.1") or {}
    c32 = idx.get("3.2") or {}
    c41 = idx.get("4.1") or {}
    c42 = idx.get("4.2") or {}

    if mid in ("", "none"):
        return None

    if mid == "circuit_breaker_status":
        return _circuit_breaker_status(c12)
    if mid == "black_swan_news":
        ni = _i(c12.get("News_Impact_Score"), 0)
        et = str(c12.get("Event_Type") or "")
        return bool(ni >= 80 or "Black Swan" in et)

    if mid == "mon_liquidity_score":
        return _i(c11.get("Liquidity_Score"), 0)
    if mid == "mon_macro_regime_state":
        return _i(c11.get("macro_regime_state"), 1)

    if mid == "news_impact":
        return _i(c12.get("News_Impact_Score"), 0)
    if mid == "news_event_type":
        return str(c12.get("Event_Type") or "")

    if mid == "pattern_setup":
        return _i(c21.get("Setup_Score"), 0)
    if mid == "pattern_name":
        return str(c21.get("pattern") or "")

    if mid == "alpha_z":
        z = c22.get("cross_sectional_z_score")
        return None if z is None else _f(z, 0.0)
    if mid == "alpha_signal_label":
        return str(c22.get("alpha_signal") or "")
    if mid == "alpha_strong_buy":
        return "Strong Buy" in str(c22.get("alpha_signal") or "")
    if mid == "alpha_strong_sell":
        return "Strong Sell" in str(c22.get("alpha_signal") or "")
    if mid == "factor_confluence":
        return _i(c22.get("Factor_Confluence"), 0)

    if mid.startswith("ta_"):
        sub = mid[3:]
        ti = c23.get("ta_indicators") if isinstance(c23.get("ta_indicators"), dict) else {}
        if not sub or sub not in ti:
            return None
        v = ti.get(sub)
        if v is None:
            return None
        if isinstance(v, bool):
            return v
        if isinstance(v, (int, float)):
            return float(v)
        return v

    if mid == "retail_fomo":
        return _i(c31.get("FOMO_Level"), 0)
    if mid == "retail_div":
        return bool(c31.get("Divergence_Warning"))
    if mid == "retail_sent_z":
        return _f(c31.get("sentiment_z_score"), 0.0)

    if mid == "pro_bias":
        return _i(c32.get("Pro_Bias"), 0)
    if mid == "pro_etf_trend":
        return str(c32.get("ETF_Trend") or "")

    if mid == "whale_dump_prob":
        return _f(c41.get("Dump_Probability"), 0.0)
    if mid == "whale_sell_pressure":
        return _i(c41.get("Sell_Pressure_Gauge"), 0)

    if mid == "liq_slippage":
        return _i(c42.get("Slippage_Risk_Score"), 50)
    if mid == "liq_imbalance":
        oi = c42.get("Order_Imbalance")
        return None if oi is None else _f(oi, 0.0)
    if mid == "liq_poc_price":
        p = c42.get("POC_Price")
        return None if p is None else _f(p, 0.0)

    # Architect-style path string stored as metric_id: map common tokens
    if "amihud" in mid or "liquidity_z" in mid:
        z = c22.get("cross_sectional_z_score")
        return None if z is None else abs(_f(z, 0.0))

    return None


def eval_operator(
    value: Any, operator: str, threshold: Any, threshold_array: list[Any] | None
) -> bool:
    """Return whether ``value`` satisfies the comparison (Tier-1 rule row)."""
    op = (operator or "==").strip()
    arr = threshold_array if isinstance(threshold_array, list) else None

    if op.upper() == "IN":
        if arr is None:
            return False
        return value in arr
    if op.upper() == "NOT_IN":
        if arr is None:
            return False
        return value not in arr

    if value is None and op not in ("!=", "NE"):
        return False

    if op in ("==", "EQ"):
        return value == threshold
    if op in ("!=", "NE"):
        return value != threshold
    if op in (">", "GT"):
        try:
            return value is not None and float(value) > float(threshold)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    if op in (">=", "GTE"):
        try:
            return value is not None and float(value) >= float(threshold)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    if op in ("<", "LT"):
        try:
            return value is not None and float(value) < float(threshold)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False
    if op in ("<=", "LTE"):
        try:
            return value is not None and float(value) <= float(threshold)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return False

    return False


__all__ = ["eval_operator", "resolve_metric", "tier0_by_agent_for_ticker"]
