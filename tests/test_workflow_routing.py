"""Graph routing and compile smoke tests (no exchange I/O)."""

from langgraph.graph import END

from main import build_workflow
from schemas.state import initial_hedge_fund_state
from workflow.routing import route_after_risk_guard, route_after_risk_guard_mapping


def test_route_veto_skips_execution():
    s = initial_hedge_fund_state()
    s["is_vetoed"] = True
    assert route_after_risk_guard(s) == "end"


def test_route_approved_goes_to_execute():
    s = initial_hedge_fund_state()
    s["is_vetoed"] = False
    assert route_after_risk_guard(s) == "portfolio_execute"


def test_conditional_path_map_uses_end_sentinel():
    m = route_after_risk_guard_mapping()
    assert m["end"] is END
    assert m["portfolio_execute"] == "portfolio_execute"


def test_workflow_compiles():
    g = build_workflow()
    compiled = g.compile()
    assert compiled is not None


def test_tier1_parallel_fanout_and_fanin_edges_present():
    g = build_workflow()
    edges = g.edges
    tier1 = {
        "price_pattern",
        "sentiment",
        "stat_arb",
        "quant",
        "desk_valuation",
        "desk_liquidity",
    }
    for node in tier1:
        assert ("desk_market_scan", node) in edges
        assert (node, "desk_risk") in edges
