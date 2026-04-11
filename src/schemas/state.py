"""LangGraph state for the multi-agent trading workflow (perception, debate, risk, execution)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, NotRequired, TypedDict

# Keys that use ``Annotated[..., operator.add]`` in :class:`HedgeFundState`.
# Nodes must only *append* via these keys (return a list fragment), never return the full
# accumulated list copied from ``state`` — see LangGraph reducer semantics.
REDUCER_STATE_KEYS = frozenset(
    {"market_context", "debate_transcript", "reasoning_logs", "tier0_contracts"}
)


class HedgeFundState(TypedDict):
    """Graph state; prefer :func:`initial_hedge_fund_state` when invoking."""

    # Tier-0 perception: append-only slices (see ``REDUCER_STATE_KEYS``).
    market_context: Annotated[List[Dict[str, Any]], operator.add]
    # Canonical Tier-0 JSON contracts (one object per agent per graph step; ``tier0_contract`` schema).
    tier0_contracts: Annotated[List[Dict[str, Any]], operator.add]
    regime_score: NotRequired[int]

    # Tier-2 — debate + thesis; ``trade_intent`` filled by signal_arbitrator (``workflow.execution_intent``).
    debate_transcript: Annotated[List[Dict[str, str]], operator.add]
    proposed_signal: Dict[str, Any]
    trade_intent: NotRequired[Dict[str, Any]]

    # Tier 3 — risk veto + execution.
    risk_report: Dict[str, Any]
    is_vetoed: bool
    veto_reason: str
    execution_result: Dict[str, Any]

    reasoning_logs: Annotated[List[Dict[str, Any]], operator.add]
    run_mode: str

    shared_memory: NotRequired[Dict[str, Any]]
    policy_decision: NotRequired[Dict[str, Any]]

    # --- Pipeline workspace (P2 migration) ---------------------------------
    # Populated by the serial LangGraph in ``main.py``; later folded into ``market_context`` /
    # ``proposed_signal`` as Tier 1/2 evolve. Kept explicit for agent nodes and tests.
    ticker: NotRequired[str]
    universe: NotRequired[List[str]]
    universe_pairs: NotRequired[List[List[str]]]
    market_data: NotRequired[Dict[str, Any]]
    market_scan: NotRequired[List[Dict[str, Any]]]
    pattern_analysis: NotRequired[Dict[str, Any]]
    sentiment_analysis: NotRequired[Dict[str, Any]]
    arb_analysis: NotRequired[Dict[str, Any]]
    quant_analysis: NotRequired[Dict[str, Any]]
    valuation: NotRequired[Dict[str, Any]]
    risk: NotRequired[Dict[str, Any]]
    # Tier-0 node payloads (required for LangGraph merge; used by ``trading.desk_inputs``).
    monetary_sentinel: NotRequired[Dict[str, Any]]
    news_narrative_miner: NotRequired[Dict[str, Any]]
    pattern_recognition_bot: NotRequired[Dict[str, Any]]
    statistical_alpha_engine: NotRequired[Dict[str, Any]]
    technical_ta_engine: NotRequired[Dict[str, Any]]
    retail_hype_tracker: NotRequired[Dict[str, Any]]
    pro_bias_analyst: NotRequired[Dict[str, Any]]
    whale_behavior_analyst: NotRequired[Dict[str, Any]]
    liquidity_order_flow: NotRequired[Dict[str, Any]]
    proposal: NotRequired[Dict[str, Any]]
    risk_guard: NotRequired[Dict[str, Any]]
    portfolio: NotRequired[Dict[str, Any]]
    liquidity: NotRequired[Dict[str, Any]]


def initial_hedge_fund_state(
    run_mode: str = "paper",
    *,
    ticker: str = "BTC/USDT",
    proposed_signal: Dict[str, Any] | None = None,
) -> HedgeFundState:
    """Defaults for ``invoke``: empty lists, no veto, optional ``proposed_signal``."""
    return HedgeFundState(
        market_context=[],
        tier0_contracts=[],
        debate_transcript=[],
        proposed_signal=proposed_signal if proposed_signal is not None else {},
        trade_intent={},
        risk_report={},
        is_vetoed=False,
        veto_reason="",
        execution_result={},
        reasoning_logs=[],
        run_mode=run_mode,
        shared_memory={},
        ticker=ticker,
        universe=[ticker],
        universe_pairs=[],
        market_data={},
        market_scan=[],
        pattern_analysis={},
        sentiment_analysis={},
        arb_analysis={},
        quant_analysis={},
        valuation={},
        risk={},
        proposal={},
        risk_guard={},
        portfolio={},
        liquidity={},
    )


__all__ = ["HedgeFundState", "REDUCER_STATE_KEYS", "initial_hedge_fund_state"]
