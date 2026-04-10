"""Tier-2 (debate / arbitration) helpers: Tier-0 evidence lines + legacy score bundle.

Keeps debate and LLM prompts grounded in the same ``tier0_contracts`` the Tier-1 applier uses.
"""

from __future__ import annotations

import math
from typing import Any

from schemas.tier0_contract import tier0_consensus_for_arbitrator, tier0_contracts_by_agent


def compact_tier0_for_prompt(state: dict[str, Any]) -> dict[str, Any]:
    """Per-agent scalar snapshot for LLM / logs (avoids huge nested blobs)."""
    idx = tier0_contracts_by_agent(state)
    compact: dict[str, Any] = {}
    for aid, row in sorted(idx.items()):
        if not isinstance(row, dict):
            continue
        entry: dict[str, Any] = {
            "agent": aid,
            "ticker": row.get("ticker"),
            "status": row.get("status"),
        }
        for k, v in row.items():
            if k in ("schema_version", "agent", "ticker", "status", "ta_indicators"):
                continue
            if isinstance(v, (int, float, str, bool)) or v is None:
                entry[k] = v
        if aid == "2.3" and isinstance(row.get("ta_indicators"), dict):
            ti = row["ta_indicators"]
            pick = ("rsi", "macd_hist", "macd", "macd_signal", "adx", "ema", "atr", "cci")
            entry["ta_indicators"] = {k: ti[k] for k in pick if k in ti and ti[k] is not None}
        compact[aid] = entry
    return compact


def _f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def bull_evidence_lines(state: dict[str, Any]) -> list[str]:
    """Constructive thesis lines from Tier-0 contracts (primary ticker rows)."""
    idx = tier0_contracts_by_agent(state)
    lines: list[str] = []

    m = idx.get("1.1") or {}
    if m.get("macro_regime_state") == 2:
        lines.append(f"Macro risk-on (liquidity_score={m.get('Liquidity_Score')}, regime_state=2).")
    n = idx.get("1.2") or {}
    ni = int(n.get("News_Impact_Score") or 0)
    if ni < 40:
        lines.append(f"News impact contained (News_Impact_Score={ni}).")

    p = idx.get("2.1") or {}
    setup = int(p.get("Setup_Score") or 0)
    if setup >= 55:
        lines.append(f"Pattern setup supportive (Setup_Score={setup}).")

    a = idx.get("2.2") or {}
    if "Strong Buy" in str(a.get("alpha_signal") or ""):
        lines.append("Statistical alpha labels Strong Buy.")

    t = idx.get("2.3") or {}
    ti = t.get("ta_indicators") if isinstance(t.get("ta_indicators"), dict) else {}
    rsi = ti.get("rsi")
    if rsi is not None and not (isinstance(rsi, float) and math.isnan(rsi)):
        rf = float(rsi)
        if rf <= 35:
            lines.append(f"TA RSI oversold ({rf:.1f}) — mean-reversion / bounce context.")
        elif rf < 70:
            lines.append(f"TA RSI not stretched ({rf:.1f}).")
    mh = ti.get("macd_hist")
    if mh is not None and _f(mh) > 0:
        lines.append(f"TA MACD histogram positive ({mh}).")

    r = idx.get("3.1") or {}
    fomo = int(r.get("FOMO_Level") or 0)
    if fomo < 75 and not r.get("Divergence_Warning"):
        lines.append(f"Retail not in extreme FOMO (FOMO_Level={fomo}).")

    pb = idx.get("3.2") or {}
    if str(pb.get("ETF_Trend") or "") == "Accumulation":
        lines.append("Institutional ETF trend: Accumulation.")

    w = idx.get("4.1") or {}
    dump = _f(w.get("Dump_Probability"), 0.0)
    if dump < 0.45:
        lines.append(f"Whale dump probability moderate ({dump:.2f}).")

    liq = idx.get("4.2") or {}
    slip = int(liq.get("Slippage_Risk_Score") or 0)
    if slip < 75:
        lines.append(f"Execution slippage risk acceptable (Slippage_Risk_Score={slip}).")

    return lines


def bear_evidence_lines(state: dict[str, Any]) -> list[str]:
    """Risk / skepticism lines from Tier-0 contracts."""
    idx = tier0_contracts_by_agent(state)
    lines: list[str] = []

    m = idx.get("1.1") or {}
    if m.get("macro_regime_state") == 0:
        lines.append(
            f"Macro risk-off (liquidity_score={m.get('Liquidity_Score')}, regime_state=0)."
        )

    n = idx.get("1.2") or {}
    ni = int(n.get("News_Impact_Score") or 0)
    et = str(n.get("Event_Type") or "")
    if ni >= 55 or "Black Swan" in et:
        lines.append(f"Headline risk elevated (News_Impact_Score={ni}, Event_Type={et}).")

    p = idx.get("2.1") or {}
    setup = int(p.get("Setup_Score") or 0)
    if setup < 45 and setup > 0:
        lines.append(f"Pattern setup weak (Setup_Score={setup}).")

    a = idx.get("2.2") or {}
    if "Strong Sell" in str(a.get("alpha_signal") or ""):
        lines.append("Statistical alpha labels Strong Sell.")

    t = idx.get("2.3") or {}
    ti = t.get("ta_indicators") if isinstance(t.get("ta_indicators"), dict) else {}
    rsi = ti.get("rsi")
    if rsi is not None and not (isinstance(rsi, float) and math.isnan(rsi)) and float(rsi) >= 70:
        lines.append(f"TA RSI stretched ({float(rsi):.1f}) — pullback risk.")
    mh = ti.get("macd_hist")
    if mh is not None and _f(mh) < 0:
        lines.append(f"TA MACD histogram negative ({mh}).")

    r = idx.get("3.1") or {}
    if r.get("Divergence_Warning") and int(r.get("FOMO_Level") or 0) >= 80:
        lines.append("Retail hype + divergence warning.")

    pb = idx.get("3.2") or {}
    if str(pb.get("ETF_Trend") or "") == "Distribution":
        lines.append("Institutional ETF trend: Distribution.")

    w = idx.get("4.1") or {}
    dump = _f(w.get("Dump_Probability"), 0.0)
    if dump >= 0.45:
        lines.append(f"Whale dump probability elevated ({dump:.2f}).")

    liq = idx.get("4.2") or {}
    slip = int(liq.get("Slippage_Risk_Score") or 0)
    if slip >= 75:
        lines.append(f"Execution slippage risk high (Slippage_Risk_Score={slip}).")

    return lines


def compute_legacy_arbitrator_scores(state: dict[str, Any]) -> dict[str, Any]:
    """Same bull/bear score math as the non-Tier-1 ``signal_arbitrator`` path (for transparency)."""
    transcript = state.get("debate_transcript") or []
    bull_votes = sum(1 for x in transcript if isinstance(x, dict) and x.get("speaker") == "bull")
    bear_votes = sum(1 for x in transcript if isinstance(x, dict) and x.get("speaker") == "bear")
    risk_analysis = ((state.get("risk") or {}).get("analysis")) or {}
    high_vol_assets = sum(
        1
        for item in risk_analysis.values()
        if isinstance(item, dict) and float(item.get("volatility", 0.0)) >= 0.01
    )
    sentiment_score = float(
        ((state.get("sentiment_analysis") or {}).get("sentiment_score")) or 50.0
    )

    bull_score = bull_votes + (1 if sentiment_score >= 55 else 0)
    bear_score = bear_votes + (1 if high_vol_assets >= 1 else 0)

    tc = tier0_consensus_for_arbitrator(state)
    bull_score += int(tc.get("bull_tilt") or 0)
    bear_score += int(tc.get("bear_tilt") or 0)
    if tc.get("block_aggressive_long"):
        bear_score += 1
    if sentiment_score <= 45:
        bear_score += 1

    return {
        "bull_votes": bull_votes,
        "bear_votes": bear_votes,
        "bull_score": bull_score,
        "bear_score": bear_score,
        "high_vol_assets": high_vol_assets,
        "sentiment_score": sentiment_score,
        "tier0_consensus": tc,
    }


def build_synthesis_board(state: dict[str, Any]) -> dict[str, Any]:
    """Deterministic bull/bear evidence + consensus snapshot for trace UI (no extra LLM).

    Mirrors the hooks fed to the optional LLM arbitrator so operators see the same
    thesis the chair used, rendered as a two-column evidence board.
    """
    ticker = str(state.get("ticker") or "BTC/USDT")
    bull_lines = bull_evidence_lines(state)
    bear_lines = bear_evidence_lines(state)
    legacy = compute_legacy_arbitrator_scores(state)
    tc = legacy.get("tier0_consensus") or {}

    def _placeholder(side: str) -> str:
        return f"No {side} desk lines fired this bar — filters are quiet or inputs are balanced."

    bull_ui = bull_lines[:20] if bull_lines else [_placeholder("constructive")]
    bear_ui = bear_lines[:20] if bear_lines else [_placeholder("defensive")]
    total = max(1, int(legacy.get("bull_score") or 0) + int(legacy.get("bear_score") or 0))
    bull_w = int(legacy.get("bull_score") or 0) / total

    return {
        "schema_version": "1.0",
        "kind": "synthesis_board",
        "ticker": ticker,
        "headline": "Evidence board — desk signals the chair synthesizes",
        "bull_case": {
            "label": "Constructive",
            "lines": bull_ui,
            "signal_count": len(bull_lines),
        },
        "bear_case": {
            "label": "Defensive",
            "lines": bear_ui,
            "signal_count": len(bear_lines),
        },
        "consensus": {
            "summary": str(tc.get("summary") or ""),
            "bull_tilt": tc.get("bull_tilt"),
            "bear_tilt": tc.get("bear_tilt"),
            "block_aggressive_long": bool(tc.get("block_aggressive_long")),
        },
        "scores": {
            "bull_score": int(legacy.get("bull_score") or 0),
            "bear_score": int(legacy.get("bear_score") or 0),
            "sentiment_score": float(legacy.get("sentiment_score") or 50.0),
            "bull_weight": round(bull_w, 3),
        },
    }


__all__ = [
    "bear_evidence_lines",
    "build_synthesis_board",
    "bull_evidence_lines",
    "compact_tier0_for_prompt",
    "compute_legacy_arbitrator_scores",
]
