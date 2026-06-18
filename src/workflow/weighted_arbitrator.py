"""Weighted Convergence Arbitrator — LangGraph node.

This module implements the ``weighted_convergence`` arbitrator mode specified
in the v4 AI-MM config. It replaces the legacy "signal_arbitrator" LLM path
with a deterministic weighted formula:

  composite   = Σ(agent_weight × Σ(factor_weight × factor_signal_normalized))
  confidence  = |composite_magnitude| × min(1.0, 0.5 + consensus_ratio × 0.5)

The node is a drop-in replacement for ``signal_arbitrator_llm`` in the LangGraph
workflow. It reads Tier-0 contracts from the state, computes weighted signals,
applies decision thresholds, and produces a ``proposed_signal`` + ``trade_intent``
identical in shape to the LLM path output.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from llm.agent_llm_client import check_api_key, infer_agent
from schemas.arbitration import ArbitrationResult
from schemas.state import HedgeFundState
from schemas.tier0_contract import tier0_contracts_by_agent
from workflow.execution_intent import derive_trade_intent
from workflow.tier2_context import build_synthesis_board
from workflow.weight_assigner import compute_weighted_arbitration

logger = logging.getLogger(__name__)

# v4 config defaults (configurable via env / overrides)
_V4_DECISION_THRESHOLD: dict[str, Any] = {
    "buy": {"min_composite": 53, "min_confidence": 10},
    "sell": {"max_composite": 47, "min_confidence": 10},
    "hold": {"else": True},
    "alignment_gating": {
        "enabled": True,
        "min_factors_for_directional": 3,
        "risk_override_if_blocked": True,
    },
}

_V4_DISABLED_AGENTS: set[str] = {"4.1"}  # Whale Behavior disabled by default

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
    state: HedgeFundState,
) -> dict[str, Any]:
    """Map ArbitrationResult → proposed_signal (same shape as LLM path)."""
    # Map composite to stance string for execution_intent
    stance = result.stance  # "bullish" | "bearish" | "neutral"
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
            "mode": _resolve_arbitrator_mode(state),
        },
    }


def _resolve_agent_weights(state: HedgeFundState) -> dict[str, float]:
    """Resolve effective agent weights, supporting Profile Agent injection.

    Priority:
    1. ``state.profile_weights`` (from Profile Agent) — full override
    2. ``_V4_AGENT_WEIGHTS`` — built-in default

    Returns a copy safe for mutation.
    """
    profile = state.get("profile_weights") or {}
    if profile:
        merged = dict(_V4_AGENT_WEIGHTS)
        merged.update(profile)
        # Re-normalise to sum 1.0
        total = sum(merged.values())
        if total > 0:
            return {k: round(v / total, 4) for k, v in merged.items()}
    return dict(_V4_AGENT_WEIGHTS)


def _resolve_arbitrator_mode(state: HedgeFundState) -> str:
    """Resolve the arbitrator mode.

    Priority:
    1. ``state.arbitrator_mode`` (from runtime settings)
    2. Deploy config active file
    3. Default: ``weighted_convergence``

    When ``AI_MARKET_MAKER_USE_LLM=1`` (set by ``--llm``) but no deploy
    config is found, raises a clear error with remediation instructions.
    """
    mode = state.get("arbitrator_mode") or ""
    if mode in ("agent_llm", "weighted_convergence"):
        return mode
    try:
        from config.deploy_loader import get_arbitrator_mode

        deploy_mode = get_arbitrator_mode()
        if deploy_mode in ("agent_llm", "weighted_convergence"):
            return deploy_mode
    except Exception:
        pass

    llm_flag = os.environ.get("AI_MARKET_MAKER_USE_LLM", "0") == "1"
    if llm_flag:
        cfg_path = os.environ.get("AIMM_DEPLOY_CONFIG_PATH", "config/deploy.active.json")
        raise RuntimeError(
            f"--llm mode requires a deploy config. File not found: {cfg_path}.\n"
            f"To fix:\n"
            f"  1. Copy the example: cp config/deploy.example.json {cfg_path}\n"
            f"  2. Edit {cfg_path} to match your agent topology, or\n"
            f"  3. Set AIMM_DEPLOY_CONFIG_PATH to a custom path."
        )

    return "weighted_convergence"


def _get_llm_enabled_agents(state: HedgeFundState) -> list[str]:
    """Get agents with llm_enabled=True.

    Priority:
    1. ``AIMM_LLM_AGENTS`` env var — comma-separated agent IDs
       (e.g. ``AIMM_LLM_AGENTS=2.1,2.3``). Overrides deploy config.
    2. ``config/deploy.active.json`` → ``agents[id].llm_enabled: true``
    3. If neither is set, all agents are LLM-enabled (full-agentic).
    """
    # 1. Env var override (highest priority)
    env_agents = os.environ.get("AIMM_LLM_AGENTS", "").strip()
    if env_agents:
        return [a.strip() for a in env_agents.split(",") if a.strip()]

    # 2. Deploy config
    try:
        from config.deploy_loader import get_deploy_agents

        deploy_agents = get_deploy_agents()
        if deploy_agents:
            enabled = []
            for aid, cfg in deploy_agents.items():
                if isinstance(cfg, dict) and cfg.get("llm_enabled", False):
                    enabled.append(aid)
            return enabled
    except Exception:
        pass

    # 3. Full-agentic: all known agents (from agent_llm_client)
    _KNOWN_AGENTS = ["1.1", "1.2", "2.1", "2.2", "2.3", "3.1", "3.2", "4.1", "4.2"]
    return list(_KNOWN_AGENTS)


def _tier0_contracts_by_agent(state: HedgeFundState) -> dict[str, dict[str, Any]]:
    """Index tier0_contracts list by agent ID for fast lookup."""
    contracts = state.get("tier0_contracts") or []
    if not isinstance(contracts, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for c in contracts:
        if isinstance(c, dict):
            aid = c.get("agent", c.get("agent_id", ""))
            if aid:
                result[aid] = c
    return result


def _inject_llm_signals(state: HedgeFundState) -> HedgeFundState:
    """Run LLM inference for each enabled agent when mode is agent_llm."""
    mode = _resolve_arbitrator_mode(state)
    if mode != "agent_llm":
        return state

    key_err = check_api_key()
    if key_err:
        raise RuntimeError(f"arbitrator_mode=agent_llm but no LLM API key: {key_err}")

    llm_agents = _get_llm_enabled_agents(state)
    if not llm_agents:
        return state

    logger.info(
        "agent_llm mode: running LLM inference for %d agents: %s",
        len(llm_agents),
        llm_agents,
    )
    deterministic = _tier0_contracts_by_agent(state)
    primary_ticker = state.get("ticker", "")

    for agent_id in llm_agents:
        det_contract = deterministic.get(agent_id)
        try:
            llm_result = infer_agent(
                agent_id,
                dict(state),
                deterministic_contract=det_contract,
                ticker=primary_ticker,
            )
            tier0 = list(state.get("tier0_contracts") or [])
            replaced = False
            for i, c in enumerate(tier0):
                if isinstance(c, dict) and c.get("agent", "") == agent_id:
                    tier0[i] = dict(llm_result)
                    replaced = True
                    break
            if not replaced:
                tier0.append(dict(llm_result))
            state = dict(state)
            state["tier0_contracts"] = tier0
        except Exception as e:
            logger.error("agent_llm: inference failed for agent %s: %s", agent_id, e)
            if "API key" in str(e):
                raise
            error_signal = {
                "agent": agent_id,
                "agent_id": agent_id,
                "source": "error",
                "llm_enabled": True,
                "llm_error": str(e),
                "composite": 50,
                "confidence": 0.0,
            }
            tier0 = list(state.get("tier0_contracts") or [])
            for i, c in enumerate(tier0):
                if isinstance(c, dict) and c.get("agent", "") == agent_id:
                    tier0[i] = error_signal
                    break
            else:
                tier0.append(error_signal)
            state = dict(state)
            state["tier0_contracts"] = tier0

    state["arbitrator_mode"] = "agent_llm"
    return state


def weighted_arbitrator_node(state: HedgeFundState) -> dict[str, Any]:
    """LangGraph node: weighted convergence arbitrator (supports agent_llm mode).

    Reads:
      - ``tier0_contracts`` from state
      - ``profile_weights`` (optional) — personalised weights from Profile Agent
      - ``run_mode`` for context

    Writes:
      - ``proposed_signal`` — same shape as ``signal_arbitrator_llm``
      - ``trade_intent``   — derived via ``derive_trade_intent``
      - ``reasoning_logs`` — per-agent scores + final decision
    """
    # agent_llm mode: inject LLM signals before arbitration
    state = _inject_llm_signals(state)

    # Resolve weights (supports Profile Agent injection)
    agent_weights = _resolve_agent_weights(state)
    profile_id = state.get("profile_id") or ""

    # Check if tier0 contracts exist
    idx = tier0_contracts_by_agent(state)
    if not idx:
        # Fallback: no Tier-0 data, return neutral
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

    proposed_signal = _arbitration_to_proposed_signal(result, state)
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
                "arbitrator_mode": _resolve_arbitrator_mode(state),
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

    # Per-agent reasoning entries for transparency
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
                    "arbitrator_mode": _resolve_arbitrator_mode(state),
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
