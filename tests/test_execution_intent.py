"""workflow.execution_intent — thesis → BUY/SELL/HOLD adapter."""

from __future__ import annotations

from dataclasses import replace

import pytest

from config.fund_policy import load_fund_policy
from workflow.execution_intent import derive_trade_intent


def _state_backtest():
    return {
        "ticker": "BTC/USDT",
        "run_mode": "backtest",
        "shared_memory": {"backtest": {"cash": 10_000.0, "qty": 0.0}},
        "market_data": {
            "BTC/USDT": {"ohlcv": [[0, 1, 1, 1, 50_000.0, 1.0]]},
        },
    }


def test_bullish_above_threshold_buy(monkeypatch: pytest.MonkeyPatch):
    # Single-source-of-truth policy loader: patch at module boundary for unit tests.
    p = replace(load_fund_policy(), max_leverage=1.0, intent_notional_fraction=0.10)
    import workflow.execution_intent as ei

    monkeypatch.setattr(ei, "load_fund_policy", lambda: p)
    ps = {
        "action": "PROPOSAL",
        "params": {"stance": "bullish", "confidence": 0.7, "reasons": ["x"]},
    }
    intent = derive_trade_intent(_state_backtest(), ps)
    assert intent["action"] == "BUY"
    assert intent["constraints"]["max_notional_usd"] == 1000.0
    assert intent["meta"]["source"] == "execution_intent_v1"


def test_neutral_or_low_confidence_hold():
    """When not flat, confidence below policy threshold → HOLD."""
    pol = load_fund_policy()
    actual_min_c = pol.min_confidence_directional

    # State has a position (not flat), so the book threshold (min_c) applies.
    state = {
        "ticker": "BTC/USDT",
        "run_mode": "backtest",
        "shared_memory": {"backtest": {"cash": 10_000.0, "qty": 0.5}},
        "market_data": {
            "BTC/USDT": {"ohlcv": [[0, 1, 1, 1, 50_000.0, 1.0]]},
        },
    }
    ps = {"params": {"stance": "bullish", "confidence": actual_min_c - 0.01}}
    result = derive_trade_intent(state, ps)
    assert result["action"] == "HOLD", (
        f"Expected HOLD when holding qty=0.5 and conf={actual_min_c - 0.01} < {actual_min_c}"
    )


def test_flat_book_low_confidence_entry():
    """Flat book with directional-but-low confidence → BUY via flat-book policy."""
    # The flat-book threshold is 0.03 (TA-alone signal on trending data).
    # Test that conf=0.04 passes but conf=0.02 holds.
    ps_pass = {"params": {"stance": "bullish", "confidence": 0.04}}
    r_pass = derive_trade_intent(_state_backtest(), ps_pass)
    assert r_pass["action"] == "BUY", (
        f"Expected BUY with conf=0.04: got {r_pass['action']} "
        f"(min={r_pass['meta'].get('effective_min_confidence')})"
    )

    ps_hold = {"params": {"stance": "bullish", "confidence": 0.02}}
    r_hold = derive_trade_intent(_state_backtest(), ps_hold)
    assert r_hold["action"] == "HOLD", f"Expected HOLD with conf=0.02: got {r_hold['action']}"

    assert r_pass["meta"].get("is_flat") is True
    assert r_pass["meta"].get("effective_min_confidence") == 0.03


def test_bearish_sell(monkeypatch: pytest.MonkeyPatch):
    p = replace(load_fund_policy(), allows_short=True)
    import workflow.execution_intent as ei

    monkeypatch.setattr(ei, "load_fund_policy", lambda: p)
    ps = {"params": {"stance": "bearish", "confidence": 0.9, "reasons": []}}
    assert derive_trade_intent(_state_backtest(), ps)["action"] == "SELL"


def test_bearish_long_only_flat_hold(monkeypatch):
    p = replace(load_fund_policy(), allows_short=False)
    import workflow.execution_intent as ei

    monkeypatch.setattr(ei, "load_fund_policy", lambda: p)
    ps = {"params": {"stance": "bearish", "confidence": 0.9, "reasons": ["macro"]}}
    intent = derive_trade_intent(_state_backtest(), ps)
    assert intent["action"] == "HOLD"
    assert any("long-only" in r or "AIMM_ALLOW_SHORT" in r for r in intent["reasons"])


def test_bearish_long_only_flat_multi_backtest_book(monkeypatch):
    p = replace(load_fund_policy(), allows_short=False)
    import workflow.execution_intent as ei

    monkeypatch.setattr(ei, "load_fund_policy", lambda: p)
    state = {
        "ticker": "BTC/USDT",
        "run_mode": "backtest",
        "shared_memory": {
            "backtest": {
                "cash": 10_000.0,
                "positions": {"BTC/USDT": 0.0, "ETH/USDT": 0.0},
            }
        },
        "market_data": {
            "BTC/USDT": {"ohlcv": [[0, 1, 1, 1, 50_000.0, 1.0]]},
        },
    }
    ps = {"params": {"stance": "bearish", "confidence": 0.9, "reasons": []}}
    intent = derive_trade_intent(state, ps)
    assert intent["action"] == "HOLD"
    assert any("multi-asset" in r or "AIMM_ALLOW_SHORT" in r for r in intent["reasons"])
