"""Deterministic arbitrator preview (legacy scores + backtest momentum) for LLM grounding.

Lives outside ``main`` to avoid import cycles with ``llm.arbitrator_llm``.
"""

from __future__ import annotations

from typing import Any

from config.run_mode import RunMode
from schemas.state import HedgeFundState

from .tier2_context import compute_legacy_arbitrator_scores


def backtest_momentum_score_delta(state: HedgeFundState) -> tuple[int, int, str | None]:
    """Nudge bull/bear from short OHLCV drift when Tier-0/Nexus are flat (offline backtest only)."""
    if str(state.get("run_mode") or "").lower() != RunMode.BACKTEST.value:
        return (0, 0, None)
    ticker = str(state.get("ticker") or "BTC/USDT")
    md = state.get("market_data") or {}
    pair = md.get(ticker) if isinstance(md, dict) else None
    ohlcv = pair.get("ohlcv") if isinstance(pair, dict) else None
    if not isinstance(ohlcv, list) or len(ohlcv) < 2:
        return (0, 0, None)
    look = min(5, len(ohlcv))
    try:
        c0 = float(ohlcv[-look][4])
        c1 = float(ohlcv[-1][4])
    except (IndexError, TypeError, ValueError):
        return (0, 0, None)
    if c0 <= 0:
        return (0, 0, None)
    r = (c1 - c0) / c0
    if r >= 0.002:
        return (1, 0, f"backtest_momentum_r={r:.4f}")
    if r <= -0.002:
        return (0, 1, f"backtest_momentum_r={r:.4f}")
    return (0, 0, None)


def legacy_deterministic_stance_preview(state: HedgeFundState) -> dict[str, Any]:
    """Same stance the non-LLM ``signal_arbitrator`` uses when Tier-1 blueprint is **off**."""
    legacy = compute_legacy_arbitrator_scores(state)
    bull_score = int(legacy["bull_score"])
    bear_score = int(legacy["bear_score"])
    mb, ms, mnote = backtest_momentum_score_delta(state)
    bull_score += mb
    bear_score += ms
    stance = "neutral"
    if bull_score > bear_score:
        stance = "bullish"
    elif bear_score > bull_score:
        stance = "bearish"
    confidence = round(min(0.95, 0.5 + (abs(bull_score - bear_score) * 0.15)), 2)
    if stance != "neutral":
        confidence = max(0.55, confidence)
    tc = legacy.get("tier0_consensus") or {}
    return {
        "bull_score": bull_score,
        "bear_score": bear_score,
        "stance": stance,
        "confidence": confidence,
        "sentiment_score": float(legacy["sentiment_score"]),
        "momentum_note": mnote,
        "tier0_summary": tc.get("summary"),
    }


__all__ = ["backtest_momentum_score_delta", "legacy_deterministic_stance_preview"]
