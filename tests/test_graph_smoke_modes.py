from __future__ import annotations

from typing import Any, Dict, List

import pytest

import main as main_mod
from config.run_mode import RunMode
from schemas.state import initial_hedge_fund_state


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
        # Always propose a tiny order; execution is routed through NexusAdapter in main.py.
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


@pytest.mark.parametrize("mode", [RunMode.BACKTEST.value, RunMode.PAPER.value])
def test_graph_smoke_runs_without_network(monkeypatch, mode: str):
    # Avoid ccxt + network by swapping agents with stubs.
    monkeypatch.setattr(main_mod, "MarketScanAgent", _StubMarketScanAgent)
    monkeypatch.setattr(main_mod, "PortfolioManagementAgent", _StubPortfolioManagementAgent)

    state = initial_hedge_fund_state(run_mode=mode, ticker="BTC/USDT")
    # Backtest path uses injected data; include minimal shape.
    state["market_data"] = {"BTC/USDT": {"status": "success", "ohlcv": [[0, 0, 0, 0, 100.0, 1.0]]}}

    app = main_mod.build_workflow().compile()
    out = app.invoke(state)

    assert out["run_mode"] == mode
    assert isinstance(out.get("reasoning_logs") or [], list)
    assert "execution_result" in out
