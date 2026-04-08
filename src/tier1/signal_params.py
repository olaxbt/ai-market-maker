"""Map Tier-1 ExecutionPayload → ``proposed_signal.params`` fragment (testable without ``main``)."""

from __future__ import annotations

from typing import Any

from tier1.models import ExecutionPayload


def build_tier1_proposed_params(
    ep: ExecutionPayload,
    *,
    tier0_summary: str,
    legacy_bull_score: int | None = None,
    legacy_bear_score: int | None = None,
) -> dict[str, Any]:
    """Return params dict for ``signal_arbitrator`` when Tier-1 preset/blueprint is active.

    Bull/bear debate nodes were removed from the graph; ``legacy_*`` scores come from
    ``compute_legacy_arbitrator_scores`` (Tier-0 consensus + risk + sentiment only).

    When ``legacy_*`` scores are passed, they are recorded for audit only; **stance and
    confidence still come from the Tier-1 applier** (deterministic policy override).
    ``workflow.execution_intent.derive_trade_intent`` maps stance → BUY/SELL/HOLD for execution.
    """
    tier1_dump = ep.model_dump(mode="json")
    sig = ep.signal
    if sig == "VETO":
        stance = "neutral"
        confidence = 0.35
    elif sig == "EXECUTE_LONG":
        stance = "bullish"
        confidence = round(max(0.55, min(0.95, ep.conviction_score / 100.0)), 2)
    elif sig == "EXECUTE_SHORT":
        stance = "bearish"
        confidence = round(max(0.55, min(0.95, ep.conviction_score / 100.0)), 2)
    else:
        stance = "neutral"
        confidence = round(min(0.52, max(0.35, ep.conviction_score / 100.0)), 2)

    reasons = [
        f"tier1_signal={sig}",
        f"tier1_conviction={ep.conviction_score}",
        f"tier0_consensus={tier0_summary}",
        "debate_layer=removed",
    ]
    if ep.veto_rule_triggered:
        reasons.append(f"tier1_veto={ep.veto_rule_triggered}")
    if legacy_bull_score is not None and legacy_bear_score is not None:
        reasons.append(f"legacy_bull_score={legacy_bull_score}")
        reasons.append(f"legacy_bear_score={legacy_bear_score}")
    reasons.append("stance_sources=tier1_applier+tier0+legacy_synthesis")
    reasons.append("tier1_policy=applier_overrides_legacy_arbitrator_scores")

    return {
        "stance": stance,
        "confidence": confidence,
        "reasons": reasons,
        "debate_entries": 0,
        "tier1_execution": tier1_dump,
    }


__all__ = ["build_tier1_proposed_params"]
