"""Tier-2 adversarial nodes (bull/bear/arbitrator) behavior tests."""

from main import bear_case, bull_case, signal_arbitrator
from schemas.state import initial_hedge_fund_state


def test_bull_and_bear_append_debate_transcript_entries():
    s = initial_hedge_fund_state()
    s["sentiment_analysis"] = {"sentiment_score": 60}
    s["quant_analysis"] = {"analysis": {"BTC/USDT": {"macd_signal": "buy"}}}
    s["risk"] = {"analysis": {"BTC/USDT": {"volatility": 0.02}}}
    s["liquidity"] = {"analysis": {"BTC/USDT": {"spread": 0.01}}}

    bull = bull_case(s)
    bear = bear_case(s)
    assert bull["debate_transcript"][0]["speaker"] == "bull"
    assert bear["debate_transcript"][0]["speaker"] == "bear"


def test_signal_arbitrator_outputs_structured_proposed_signal():
    s = initial_hedge_fund_state()
    s["debate_transcript"] = [
        {"speaker": "bull", "stance": "long-bias", "argument": "uptrend"},
        {"speaker": "bear", "stance": "risk-off", "argument": "volatility high"},
    ]
    s["sentiment_analysis"] = {"sentiment_score": 58}
    s["risk"] = {"analysis": {"BTC/USDT": {"volatility": 0.012}}}

    out = signal_arbitrator(s)
    proposed_signal = out["proposed_signal"]
    assert proposed_signal["action"] == "PROPOSAL"
    assert isinstance(proposed_signal["params"], dict)
    assert proposed_signal["meta"]["source"] == "signal_arbitrator"
