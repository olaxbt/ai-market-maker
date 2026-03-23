"""Tests for :class:`schemas.state.HedgeFundState` and initial state factory."""

from schemas.state import REDUCER_STATE_KEYS, HedgeFundState, initial_hedge_fund_state


def test_initial_state_has_required_tier_keys():
    s = initial_hedge_fund_state(run_mode="paper", ticker="ETH/USDT")
    assert s["run_mode"] == "paper"
    assert s["ticker"] == "ETH/USDT"
    assert s["is_vetoed"] is False
    assert s["veto_reason"] == ""
    assert s["market_context"] == []
    assert s["debate_transcript"] == []
    assert s["reasoning_logs"] == []
    assert s["proposed_signal"] == {}
    assert s["risk_report"] == {}
    assert s["execution_result"] == {}


def test_reducer_keys_documented():
    assert "market_context" in REDUCER_STATE_KEYS
    assert "reasoning_logs" in REDUCER_STATE_KEYS


def test_hedge_fund_state_is_typed_dict():
    # Runtime check: TypedDict instances are dicts with expected keys
    s: HedgeFundState = initial_hedge_fund_state()
    assert isinstance(s, dict)
    assert "run_mode" in s
