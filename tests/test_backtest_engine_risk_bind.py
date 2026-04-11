"""Backtest engine: intrabar stop / take-profit bind on the sim book (authoritative fills)."""

from __future__ import annotations

import pytest

from backtest.engine import BacktestEngine
from config.fund_policy import load_fund_policy


def test_forced_stop_triggers_on_bar_low(monkeypatch):
    monkeypatch.setenv("AIMM_STOP_LOSS_PCT", "0.05")
    monkeypatch.setenv("AIMM_TAKE_PROFIT_PCT", "0")
    eng = BacktestEngine()
    pol = load_fund_policy()
    # entry 100, stop 5% -> 95; low 84 breaches
    bar = [0, 100.0, 100.0, 84.0, 90.0, 1.0]
    o, ref = eng._forced_risk_smart_order(bar, pre_qty=1.0, pre_entry=100.0, policy=pol)
    assert o is not None
    assert o["side"] == "sell"
    assert o["qty"] == pytest.approx(1.0)
    assert (o.get("intent") or {}).get("category") == "risk_stop_loss"
    assert ref == pytest.approx(min(90.0, 95.0))


def test_forced_tp_triggers_on_bar_high(monkeypatch):
    monkeypatch.setenv("AIMM_STOP_LOSS_PCT", "0")
    monkeypatch.setenv("AIMM_TAKE_PROFIT_PCT", "0.08")
    eng = BacktestEngine()
    pol = load_fund_policy()
    # entry 100, tp 8% -> 108; high 110 hits
    bar = [0, 100.0, 110.0, 99.0, 105.0, 1.0]
    o, ref = eng._forced_risk_smart_order(bar, pre_qty=0.5, pre_entry=100.0, policy=pol)
    assert o is not None
    assert o["side"] == "sell"
    assert (o.get("intent") or {}).get("category") == "risk_take_profit"
    assert ref == pytest.approx(max(105.0, 108.0))


def test_forced_none_when_range_inside_bands(monkeypatch):
    monkeypatch.setenv("AIMM_STOP_LOSS_PCT", "0.05")
    monkeypatch.setenv("AIMM_TAKE_PROFIT_PCT", "0.08")
    eng = BacktestEngine()
    pol = load_fund_policy()
    bar = [0, 100.0, 102.0, 98.0, 101.0, 1.0]
    o, _ = eng._forced_risk_smart_order(bar, pre_qty=1.0, pre_entry=100.0, policy=pol)
    assert o is None
