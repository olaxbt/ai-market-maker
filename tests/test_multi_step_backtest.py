"""Multi-step bar backtest: synthetic bars + stub agents (no network)."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

import main as main_mod
from backtest.bars import synthetic_ohlcv_bars
from backtest.loop import run_multi_step_backtest

pytestmark = pytest.mark.slow


class _StubMarketScanAgent:
    def __init__(self, *args, **kwargs):
        pass

    def fetch_data(self, ticker: str, timeframe: str = "1h") -> Dict[str, Any]:
        return {
            "ticker": ticker,
            "ohlcv": [[0, 0, 0, 0, 100.0, 1.0]],
            "bids": [[99.5, 1.0]],
            "asks": [[100.5, 1.0]],
            "status": "success",
        }

    def scan_meme_coins(self) -> List[Dict[str, Any]]:
        return []


class _StubPortfolioManagementAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, ticker: str, *args, execute: bool = True, **kwargs) -> Dict[str, Any]:
        return {
            "status": "success",
            "allocations": {ticker: {"weight": 1.0, "amount": 10.0, "stop_price": 0}},
            "trades": {
                ticker: {
                    "status": "proposed",
                    "action": "buy",
                    "quantity": 0.01,
                    "reason": {"note": "stub"},
                }
            },
        }


class _StubPricePatternAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, ticker: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "ticker": ticker, "analysis": {"pattern": "stub"}}


class _StubStatArbAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(
        self, market_data: Dict[str, Any], market_scan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"pairs": []}}


class _StubQuantAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"BTC/USDT": {"macd_signal": "buy"}}}


class _StubValuationAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(
        self, market_data: Dict[str, Any], market_scan: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"BTC/USDT": {"value": 100.0}}}


class _StubLiquidityManagementAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"BTC/USDT": {"spread": 0.0001}}}


class _StubRiskManagementAgent:
    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, market_data: Dict[str, Any], valuation: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "success", "analysis": {"BTC/USDT": {"volatility": 0.001}}}


class _StubRiskGuardAgent:
    role = "agent"

    def __init__(self, *args, **kwargs):
        pass

    async def process(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "APPROVED", "risk_score": 0.1, "reasoning": {"thought": "stub approve"}}


class _StubNexusAdapter:
    def place_smart_order(self, *, symbol: str, side: str, qty: float, **kwargs) -> Dict[str, Any]:
        return {"status": "accepted", "symbol": symbol, "side": side, "qty": qty}


def test_multi_step_backtest_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "MarketScanAgent", _StubMarketScanAgent)
    monkeypatch.setattr(main_mod, "PortfolioManagementAgent", _StubPortfolioManagementAgent)
    monkeypatch.setattr(main_mod, "PricePatternAgent", _StubPricePatternAgent)
    monkeypatch.setattr(main_mod, "StatArbAgent", _StubStatArbAgent)
    monkeypatch.setattr(main_mod, "QuantAgent", _StubQuantAgent)
    monkeypatch.setattr(main_mod, "ValuationAgent", _StubValuationAgent)
    monkeypatch.setattr(main_mod, "LiquidityManagementAgent", _StubLiquidityManagementAgent)
    monkeypatch.setattr(main_mod, "RiskManagementAgent", _StubRiskManagementAgent)
    monkeypatch.setattr(main_mod, "RiskGuardAgent", _StubRiskGuardAgent)
    monkeypatch.setattr(main_mod, "get_nexus_adapter", lambda: _StubNexusAdapter())

    bars = synthetic_ohlcv_bars(40, seed=7, interval_sec=300)
    result = run_multi_step_backtest(
        ticker="BTC/USDT",
        bars=bars,
        initial_cash=10_000.0,
        fee_bps=10.0,
        interval_sec=300,
        runs_dir=tmp_path,
        max_steps=6,
    )

    assert result.summary_path.is_file()
    assert result.equity_path.is_file()
    assert result.steps == 6
    assert "sharpe" in result.metrics
    # With status=success OHLCV + backtest portfolio rules, we expect some simulated fills.
    assert result.trade_count >= 1
