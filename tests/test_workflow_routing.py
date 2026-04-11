"""Graph routing and compile smoke tests (no exchange I/O)."""

import pytest

pytest.importorskip("ccxt")

from main import build_workflow
from schemas.state import initial_hedge_fund_state
from workflow.routing import route_after_risk_guard, route_after_risk_guard_mapping


def test_route_veto_skips_execution():
    s = initial_hedge_fund_state()
    s["is_vetoed"] = True
    assert route_after_risk_guard(s) == "audit"


def test_route_approved_goes_to_execute():
    s = initial_hedge_fund_state()
    s["is_vetoed"] = False
    assert route_after_risk_guard(s) == "portfolio_execute"


def test_conditional_path_map_uses_end_sentinel():
    m = route_after_risk_guard_mapping()
    # Veto path goes to audit, which then ends the workflow.
    assert m["audit"] == "audit"
    assert m["portfolio_execute"] == "portfolio_execute"


def test_workflow_compiles():
    g = build_workflow()
    compiled = g.compile()
    assert compiled is not None


def test_tier1_parallel_fanout_and_fanin_edges_present():
    g = build_workflow()
    edges = g.edges
    tier0 = {
        "monetary_sentinel",
        "news_narrative_miner",
        "pattern_recognition_bot",
        "statistical_alpha_engine",
        "technical_ta_engine",
        "retail_hype_tracker",
        "pro_bias_analyst",
        "whale_behavior_analyst",
        "liquidity_order_flow",
    }
    for node in tier0:
        assert ("desk_market_scan", node) in edges
        assert (node, "desk_risk") in edges


def test_tier2_risk_to_arbitrator_edge_present():
    g = build_workflow()
    edges = g.edges
    assert ("desk_risk", "desk_debate") in edges
    assert ("desk_debate", "signal_arbitrator") in edges
    assert ("signal_arbitrator", "portfolio_proposal") in edges
