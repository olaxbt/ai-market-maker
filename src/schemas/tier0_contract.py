"""Canonical Tier-0 JSON contract for Tier-1 / strategy consumers.

Each perception node appends one object to ``HedgeFundState.tier0_contracts`` (reducer: list concat).
Field names follow the PM-facing examples (PascalCase scalars where specified).
"""

from __future__ import annotations

from typing import Any

# LangGraph node id -> AIMM-style agent id string
TIER0_NODE_TO_AGENT_ID: dict[str, str] = {
    "monetary_sentinel": "1.1",
    "news_narrative_miner": "1.2",
    "pattern_recognition_bot": "2.1",
    "statistical_alpha_engine": "2.2",
    "technical_ta_engine": "2.3",
    "retail_hype_tracker": "3.1",
    "pro_bias_analyst": "3.2",
    "whale_behavior_analyst": "4.1",
    "liquidity_order_flow": "4.2",
}

CONTRACT_SCHEMA_VERSION = "tier0/v1"


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _macro_regime_state(liquidity_regime: str) -> int:
    m = (liquidity_regime or "neutral").lower().replace(" ", "_")
    if m in ("risk_on", "riskon", "expansion"):
        return 2
    if m in ("risk_off", "riskoff", "contraction"):
        return 0
    return 1


def _contract_1_1(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    score = _f(analysis.get("systemic_beta_score"), 50.0)
    regime = str(analysis.get("liquidity_regime") or "neutral")
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "1.1",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "macro_regime_state": _macro_regime_state(regime),
        "regime_prob": round(min(0.99, max(0.01, score / 100.0)), 2),
        "Liquidity_Score": int(round(min(100.0, max(0.0, score)))),
    }


def _contract_1_2(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    impact = _f(analysis.get("breaker_score"), 0.0)
    if impact >= 75:
        ev = "Black Swan"
    elif impact >= 45:
        ev = "Major Catalyst"
    elif impact >= 25:
        ev = "Elevated"
    else:
        ev = "Routine"
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "1.2",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "News_Impact_Score": int(round(min(100.0, max(0.0, impact)))),
        "Event_Type": ev,
        "decay_factor": analysis.get("decay_factor"),
    }


def _contract_2_1(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    setup = _f(analysis.get("setup_confidence_score"), 0.0)
    sr = (
        analysis.get("support_resistance")
        if isinstance(analysis.get("support_resistance"), dict)
        else {}
    )
    sup = sr.get("support") if isinstance(sr, dict) else None
    kal = None
    if isinstance(sup, (int, float)):
        kal = float(sup)
    pat = analysis.get("pattern") or analysis.get("macro_regime")
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "2.1",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "Setup_Score": int(round(min(100.0, max(0.0, setup)))),
        "kalman_support": kal,
        "pattern": str(pat) if pat is not None else "unknown",
    }


def _contract_2_2(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    sig = str(analysis.get("alpha_signal") or "hold").lower()
    label_map = {
        "long_bias": "Strong Buy",
        "short_bias": "Strong Sell",
        "hold": "Hold",
    }
    alpha_label = label_map.get(sig, sig.replace("_", " ").title())
    rank = analysis.get("cross_sectional_rank")
    z = 0.0
    if analysis.get("cross_sectional_z_score") is not None:
        try:
            z = float(analysis["cross_sectional_z_score"])
        except (TypeError, ValueError):
            z = 0.0
    elif isinstance(rank, int) and rank > 0:
        z = max(-3.0, min(3.0, 3.0 - (rank - 1) * 0.15))
    conf = 50
    if isinstance(rank, int):
        if rank <= 3:
            conf = 95
        elif rank <= 10:
            conf = 75
        elif rank <= 25:
            conf = 55
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "2.2",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "Factor_Confluence": conf,
        "cross_sectional_z_score": round(z, 2) if analysis.get("status") == "success" else None,
        "alpha_signal": alpha_label,
    }


def _contract_2_3(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    """Classical TA bundle (Agent 2.3) for Tier-1 ``ta_*`` metric_ids."""
    ti = analysis.get("ta_indicators")
    if not isinstance(ti, dict):
        ti = {}
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "2.3",
        "ticker": ticker,
        "status": str(analysis.get("status") or "skipped"),
        "ta_period": analysis.get("ta_period"),
        "bars_used": analysis.get("bars"),
        "indicator_catalog_version": analysis.get("indicator_catalog_version") or "ta_bundle/v1",
        "ta_indicators": ti,
    }


def _contract_3_1(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "3.1",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "FOMO_Level": int(min(100, max(0, int(_f(analysis.get("fomo_level"), 50))))),
        "Divergence_Warning": bool(analysis.get("divergence_warning")),
        "sentiment_z_score": round(_f(analysis.get("sentiment_z_score"), 0.0), 2),
    }


def _contract_3_2(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    score = _f(analysis.get("pro_bias_score"), 50.0)
    regime = str(analysis.get("regime") or "passive_rotation").lower()
    if "accumulation" in regime:
        etf = "Accumulation"
    elif "distribution" in regime:
        etf = "Distribution"
    else:
        etf = "Neutral"
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "3.2",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "Pro_Bias": int(round(min(100.0, max(0.0, score)))),
        "ETF_Trend": etf,
        "ema_slope": analysis.get("ema_slope"),
    }


def _contract_4_1(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    dump = _f(analysis.get("dump_probability"), 0.0)
    gauge = int(round(min(100.0, max(0.0, dump * 100.0))))
    dp = str(analysis.get("dry_powder_alert") or "unknown").lower()
    if dp in ("elevated", "high"):
        dpa = "High"
    elif dp in ("low", "thin"):
        dpa = "Low"
    else:
        dpa = "Normal"
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "4.1",
        "ticker": ticker,
        "status": str(analysis.get("status") or "success"),
        "Sell_Pressure_Gauge": gauge,
        "Dump_Probability": round(dump, 2),
        "Dry_Powder_Alert": dpa,
    }


def _contract_4_2(analysis: dict[str, Any], ticker: str) -> dict[str, Any]:
    has_depth = bool(analysis.get("nexus_depth_attached"))
    st = str(analysis.get("status") or "skipped")
    slip = analysis.get("slippage_risk_score")
    if slip is None:
        slip = 40 if has_depth and st == "success" else 85
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "agent": "4.2",
        "ticker": ticker,
        "status": st,
        "Slippage_Risk_Score": int(slip) if isinstance(slip, (int, float)) else slip,
        "Order_Imbalance": analysis.get("order_imbalance"),
        "POC_Price": analysis.get("poc_price"),
    }


_BUILDERS: dict[str, Any] = {
    "1.1": _contract_1_1,
    "1.2": _contract_1_2,
    "2.1": _contract_2_1,
    "2.2": _contract_2_2,
    "2.3": _contract_2_3,
    "3.1": _contract_3_1,
    "3.2": _contract_3_2,
    "4.1": _contract_4_1,
    "4.2": _contract_4_2,
}


def build_tier0_contract_json(
    node_id: str, primary_analysis: dict[str, Any], ticker: str
) -> dict[str, Any]:
    """Map node id + primary symbol analysis dict to the canonical Tier-0 JSON object."""
    aid = TIER0_NODE_TO_AGENT_ID.get(node_id, node_id)
    fn = _BUILDERS.get(aid)
    if fn is None:
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "agent": aid,
            "ticker": ticker,
            "status": "error",
            "error": f"unknown_tier0_node:{node_id}",
        }
    return fn(primary_analysis, ticker)


def tier0_contracts_by_agent(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Last-wins index by agent id (e.g. ``1.1``) for Tier-1 convenience."""
    out: dict[str, dict[str, Any]] = {}
    for row in state.get("tier0_contracts") or []:
        if isinstance(row, dict) and row.get("agent"):
            out[str(row["agent"])] = row
    return out


def tier0_consensus_for_arbitrator(state: dict[str, Any]) -> dict[str, Any]:
    """Aggregate Tier-0 canonical contracts into bull/bear tilts for ``signal_arbitrator``.

    Uses only Tier-0 JSON fields (no raw Nexus blobs). When ``tier0_contracts`` is empty,
    returns zero tilts and ``tier0_skipped``.
    """
    idx = tier0_contracts_by_agent(state)
    if not idx:
        return {
            "bull_tilt": 0,
            "bear_tilt": 0,
            "block_aggressive_long": False,
            "parts": [],
            "summary": "tier0_skipped",
        }

    bull = 0
    bear = 0
    block = False
    parts: list[str] = []

    m = idx.get("1.1") or {}
    mrs = m.get("macro_regime_state")
    if mrs == 2:
        bull += 1
        parts.append("1.1_risk_on")
    elif mrs == 0:
        bear += 1
        parts.append("1.1_risk_off")

    n = idx.get("1.2") or {}
    try:
        ni = int(n.get("News_Impact_Score") or 0)
    except (TypeError, ValueError):
        ni = 0
    et = str(n.get("Event_Type") or "")
    if ni >= 80 or "Black Swan" in et:
        block = True
        bear += 2
        parts.append("1.2_shock")
    elif ni >= 55:
        bear += 1
        parts.append("1.2_elevated_news")

    t21 = idx.get("2.1") or {}
    try:
        setup = int(t21.get("Setup_Score") or 0)
    except (TypeError, ValueError):
        setup = 0
    if setup >= 70:
        bull += 1
        parts.append("2.1_setup")

    t22 = idx.get("2.2") or {}
    sig = str(t22.get("alpha_signal") or "")
    if "Strong Buy" in sig:
        bull += 1
        parts.append("2.2_long")
    elif "Strong Sell" in sig:
        bear += 1
        parts.append("2.2_short")

    t23 = idx.get("2.3") or {}
    ti = t23.get("ta_indicators") if isinstance(t23.get("ta_indicators"), dict) else {}
    rsi_v = ti.get("rsi")
    try:
        rsi_f = float(rsi_v) if rsi_v is not None else None
    except (TypeError, ValueError):
        rsi_f = None
    if rsi_f is not None:
        if rsi_f >= 70.0:
            bear += 1
            parts.append("2.3_rsi_stretched")
        elif rsi_f <= 30.0:
            bull += 1
            parts.append("2.3_rsi_oversold")

    r31 = idx.get("3.1") or {}
    try:
        fomo = int(r31.get("FOMO_Level") or 0)
    except (TypeError, ValueError):
        fomo = 0
    if r31.get("Divergence_Warning") and fomo >= 85:
        bear += 1
        parts.append("3.1_hype_div")

    p32 = idx.get("3.2") or {}
    etf = str(p32.get("ETF_Trend") or "")
    if etf == "Accumulation":
        bull += 1
        parts.append("3.2_accum")
    elif etf == "Distribution":
        bear += 1
        parts.append("3.2_dist")

    w41 = idx.get("4.1") or {}
    try:
        dump = float(w41.get("Dump_Probability") or 0.0)
    except (TypeError, ValueError):
        dump = 0.0
    if dump >= 0.65:
        bear += 1
        parts.append("4.1_dump")

    l42 = idx.get("4.2") or {}
    try:
        slip = int(l42.get("Slippage_Risk_Score") or 0)
    except (TypeError, ValueError):
        slip = 0
    if slip >= 80:
        bear += 1
        parts.append("4.2_slip")

    return {
        "bull_tilt": bull,
        "bear_tilt": bear,
        "block_aggressive_long": block,
        "parts": parts,
        "summary": ",".join(parts) if parts else "tier0_neutral",
    }


__all__ = [
    "CONTRACT_SCHEMA_VERSION",
    "TIER0_NODE_TO_AGENT_ID",
    "build_tier0_contract_json",
    "tier0_contracts_by_agent",
    "tier0_consensus_for_arbitrator",
]
