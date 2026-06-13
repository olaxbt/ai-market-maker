"""Weighted convergence arbitrator LangGraph node."""

from __future__ import annotations

from typing import Any

from schemas.arbitration import ArbitrationResult
from schemas.state import HedgeFundState
from schemas.tier0_contract import tier0_contracts_by_agent
from workflow.execution_intent import derive_trade_intent
from workflow.tier2_context import build_synthesis_board
from workflow.weight_assigner import compute_weighted_arbitration

# v4 defaults
_V4_DECISION_THRESHOLD: dict[str, Any] = {
    "buy": {"min_composite": 60, "min_confidence": 50},
    "sell": {"max_composite": 40, "min_confidence": 50},
    "hold": {"else": True},
    "alignment_gating": {
        "enabled": True,
        "min_factors_for_directional": 3,
        "risk_override_if_blocked": True,
    },
}

_V4_DISABLED_AGENTS: set[str] = {"4.1"}

_V4_AGENT_WEIGHTS: dict[str, float] = {
    "1.1": 0.05,
    "1.2": 0.05,
    "2.1": 0.25,
    "2.2": 0.10,
    "2.3": 0.30,
    "3.1": 0.05,
    "3.2": 0.05,
    "4.1": 0.05,
    "4.2": 0.15,
}


def _reasoning_entry(
    *,
    node: str,
    thought: str,
    decision: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = thought.strip() if isinstance(thought, str) else str(thought)
    return {
        "node": node,
        "reasoning_chain": detail,
        "thought_process": detail,
        "decision": decision,
        "extra": extra or {},
    }


def _compact_arbitration_for_reasoning(
    result: ArbitrationResult,
) -> dict[str, Any]:
    """Compact arbitration result for reasoning_logs."""
    return {
        "composite_score": result.composite_score,
        "confidence": result.confidence,
        "stance": result.stance,
        "conviction_level": result.conviction_level,
        "consensus_ratio": result.consensus_ratio,
        "buy_triggered": result.buy_triggered,
        "sell_triggered": result.sell_triggered,
        "hold_triggered": result.hold_triggered,
        "alignment_gated": result.alignment_gated,
        "reasons": result.reasons[:8],
        "agents": [
            {
                "id": s.agent_id,
                "label": s.label,
                "composite": s.composite,
                "weighted_contribution": round(s.weighted_composite, 4),
                "stance": s.stance,
                "confidence": round(s.confidence, 3),
                "enabled": s.enabled,
            }
            for s in result.agent_signals[:12]
        ],
    }


def _arbitration_to_proposed_signal(
    result: ArbitrationResult,
) -> dict[str, Any]:
    """Map ArbitrationResult to proposed_signal."""
    stance = result.stance
    confidence = result.confidence

    return {
        "action": "PROPOSAL",
        "params": {
            "stance": stance,
            "confidence": round(confidence, 4),
            "reasons": result.reasons[:12],
            "tool_events": [],
            "debate_entries": 0,
            "weighted_arbitrator": True,
            "composite_score": result.composite_score,
            "conviction_level": result.conviction_level,
            "consensus_ratio": result.consensus_ratio,
            "alignment_gated": result.alignment_gated,
            "agent_signals": [
                {
                    "agent_id": s.agent_id,
                    "label": s.label,
                    "composite": s.composite,
                    "agent_weight": s.agent_weight,
                    "weighted_composite": round(s.weighted_composite, 4),
                    "stance": s.stance,
                    "confidence": round(s.confidence, 3),
                    "factor_contributions": round(
                        sum(f.weight * f.normalized for f in s.factor_signals)
                        / max(0.001, sum(f.weight for f in s.factor_signals)),
                        4,
                    )
                    if s.factor_signals
                    else 0.5,
                }
                for s in result.agent_signals[:12]
            ],
        },
        "meta": {
            "source": "weighted_arbitrator",
            "mode": "weighted_convergence",
        },
    }


def _resolve_agent_weights(state: HedgeFundState) -> dict[str, float]:
    """Resolve agent weights; profile_weights override defaults when set."""
    profile = state.get("profile_weights") or {}
    if profile:
        merged = dict(_V4_AGENT_WEIGHTS)
        merged.update(profile)
        total = sum(merged.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in merged.items()}
    return dict(_V4_AGENT_WEIGHTS)


def weighted_arbitrator_node(state: HedgeFundState) -> dict[str, Any]:
    agent_weights = _resolve_agent_weights(state)
    profile_id = state.get("profile_id") or ""

    idx = tier0_contracts_by_agent(state)
    if not idx:
        result = ArbitrationResult(
            composite_score=0.5,
            confidence=0.0,
            stance="neutral",
            conviction_level="none",
            reasons=["weighted_arbitrator: no Tier-0 contracts available"],
            agent_signals=[],
        )
    else:
        result = compute_weighted_arbitration(
            state,
            agent_weights=agent_weights,
            disabled_agents=_V4_DISABLED_AGENTS,
            decision_threshold=_V4_DECISION_THRESHOLD,
        )

    proposed_signal = _arbitration_to_proposed_signal(result)
    intent = derive_trade_intent(state, proposed_signal)

    compact = _compact_arbitration_for_reasoning(result)
    board = build_synthesis_board(state)

    weight_source = "profile" if profile_id else "default"

    reasoning_logs = [
        _reasoning_entry(
            node="signal_arbitrator",
            thought=(
                f"Weighted convergence arbitration complete. "
                f"Stance={result.stance}, composite={result.composite_score:.4f}, "
                f"confidence={result.confidence:.4f}, conviction={result.conviction_level}."
            ),
            decision=compact,
            extra={
                "arbitrator_mode": "weighted_convergence",
                "weight_source": weight_source,
                "profile_id": profile_id if profile_id else None,
                "aligned": not result.alignment_gated,
                "buy_triggered": result.buy_triggered,
                "sell_triggered": result.sell_triggered,
                "synthesis_board_present": bool(board.get("bull_case")),
            },
        ),
        _reasoning_entry(
            node="execution_intent",
            thought="Execution intent derived from weighted arbitration composite.",
            decision=intent,
            extra={"weighted_arbitrator": True},
        ),
    ]

    for sig in result.agent_signals:
        if not sig.enabled:
            continue
        factor_breakdown = {
            f.factor_id: {
                "raw": round(f.raw_value, 4),
                "normalized": round(f.normalized, 4),
                "weight": f.weight,
            }
            for f in sig.factor_signals
        }
        reasoning_logs.append(
            _reasoning_entry(
                node="signal_arbitrator",
                thought=(
                    f"Agent [{sig.agent_id}] {sig.label}: "
                    f"composite={sig.composite:.4f}, stance={sig.stance}, "
                    f"weighted_contribution={sig.weighted_composite:.4f}"
                ),
                decision={
                    "agent_id": sig.agent_id,
                    "agent_type": sig.agent_type,
                    "label": sig.label,
                    "composite": round(sig.composite, 4),
                    "agent_weight": sig.agent_weight,
                    "weighted_composite": round(sig.weighted_composite, 4),
                    "stance": sig.stance,
                    "confidence": round(sig.confidence, 3),
                    "factor_count": len(sig.factor_signals),
                    "factor_breakdown": factor_breakdown,
                },
                extra={
                    "arbitrator_mode": "weighted_convergence",
                    "agent_id": sig.agent_id,
                },
            )
        )

    return {
        "proposed_signal": proposed_signal,
        "trade_intent": intent,
        "reasoning_logs": reasoning_logs,
        "arbitration_result": {
            "composite": result.composite_score,
            "confidence": result.confidence,
            "stance": result.stance,
            "conviction": result.conviction_level,
            "consensus_ratio": result.consensus_ratio,
            "alignment_gated": result.alignment_gated,
        },
    }


__all__ = ["weighted_arbitrator_node"]
