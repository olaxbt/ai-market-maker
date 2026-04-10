"""Deterministic routing for the LangGraph workflow (Tier 3 risk gate)."""

from __future__ import annotations

from typing import Literal

from schemas.state import HedgeFundState

RouteAfterRisk = Literal["portfolio_execute", "audit"]


def route_after_risk_guard(state: HedgeFundState) -> RouteAfterRisk:
    """If Risk Guard vetoed, skip execution and audit; otherwise continue to execution."""
    if state.get("is_vetoed"):
        return "audit"
    return "portfolio_execute"


def route_after_risk_guard_mapping() -> dict[str, str]:
    """Path map for :meth:`langgraph.graph.StateGraph.add_conditional_edges`."""
    return {"audit": "audit", "portfolio_execute": "portfolio_execute"}


__all__ = ["route_after_risk_guard", "route_after_risk_guard_mapping"]
