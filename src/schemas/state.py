"""LangGraph state for the multi-agent trading workflow (perception, debate, risk, execution)."""

from __future__ import annotations

import operator
from typing import Annotated, Any, Dict, List, NotRequired, TypedDict


class HedgeFundState(TypedDict):
    """Graph state; prefer :func:`initial_hedge_fund_state` when invoking."""

    market_context: Annotated[List[Dict[str, Any]], operator.add]
    regime_score: NotRequired[int]

    debate_transcript: Annotated[List[Dict[str, str]], operator.add]
    proposed_signal: Dict[str, Any]

    risk_report: Dict[str, Any]
    is_vetoed: bool
    veto_reason: str
    execution_result: Dict[str, Any]

    reasoning_logs: Annotated[List[Dict[str, Any]], operator.add]
    run_mode: str

    shared_memory: NotRequired[Dict[str, Any]]


def initial_hedge_fund_state(
    run_mode: str = "paper",
    *,
    proposed_signal: Dict[str, Any] | None = None,
) -> HedgeFundState:
    """Defaults for ``invoke``: empty lists, no veto, optional ``proposed_signal``."""
    return HedgeFundState(
        market_context=[],
        debate_transcript=[],
        proposed_signal=proposed_signal if proposed_signal is not None else {},
        risk_report={},
        is_vetoed=False,
        veto_reason="",
        execution_result={},
        reasoning_logs=[],
        run_mode=run_mode,
        shared_memory={},
    )


__all__ = ["HedgeFundState", "initial_hedge_fund_state"]
