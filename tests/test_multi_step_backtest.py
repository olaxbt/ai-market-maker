"""Multi-step bar backtest: synthetic bars + stub agents (no network)."""

from __future__ import annotations

from typing import Any, Dict, List

import main as main_mod
from backtest.bars import synthetic_ohlcv_bars
from backtest.loop import run_multi_step_backtest


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


def test_multi_step_backtest_writes_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(main_mod, "MarketScanAgent", _StubMarketScanAgent)
    monkeypatch.setattr(main_mod, "PortfolioManagementAgent", _StubPortfolioManagementAgent)

    bars = synthetic_ohlcv_bars(40, seed=7, interval_sec=300)
    result = run_multi_step_backtest(
        ticker="BTC/USDT",
        bars=bars,
        initial_cash=10_000.0,
        fee_bps=10.0,
        interval_sec=300,
        runs_dir=tmp_path,
        max_steps=12,
    )

    assert result.summary_path.is_file()
    assert result.equity_path.is_file()
    assert result.steps == 12
    assert "sharpe" in result.metrics
    # With status=success OHLCV + backtest portfolio rules, we expect some simulated fills.
    assert result.trade_count >= 1
