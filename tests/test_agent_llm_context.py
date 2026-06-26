"""Tests for LLM agent prompt context — simulation awareness block."""

from __future__ import annotations

from llm.agent_llm_client import _build_simulation_context


class TestSimulationContext:
    def test_non_backtest_mode_returns_empty(self):
        state = {"run_mode": "live", "shared_memory": {}}
        result = _build_simulation_context(state, "BTC/USDT")
        assert result == ""

    def test_backtest_mode_has_as_of_time(self):
        state = {
            "run_mode": "backtest",
            "ticker": "BTC/USDT",
            "shared_memory": {
                "backtest": {
                    "window_last_ts_ms": 1700000000000.0,
                    "window_len": 10,
                    "interval_sec": 86400,
                    "timeframe": "1d",
                    "run_id": "bt_12345",
                }
            },
        }
        result = _build_simulation_context(state, "BTC/USDT")
        assert "## Simulation Context" in result
        assert "Mode: backtest" in result
        assert "Bar interval: 86400s (1d)" in result
        assert "As-of bar (UTC):" in result
        assert "Run ID: bt_12345" in result
        assert "Primary ticker: BTC/USDT" in result

    def test_backtest_without_ticker_falls_back(self):
        state = {
            "run_mode": "backtest",
            "ticker": "ETH/USDT",
            "shared_memory": {
                "backtest": {
                    "window_last_ts_ms": 1700000000000.0,
                    "window_len": 5,
                    "interval_sec": 3600,
                    "timeframe": "1h",
                    "run_id": "",
                }
            },
        }
        result = _build_simulation_context(state, None)
        assert "ETH/USDT" in result
        assert "Run ID" not in result or "bt_" not in result

    def test_without_backtest_data_handles_missing(self):
        state = {
            "run_mode": "backtest",
            "ticker": "BTC/USDT",
            "shared_memory": {},
        }
        result = _build_simulation_context(state, "BTC/USDT")
        assert "## Simulation Context" in result
        assert "N/A" in result or "?" in result  # graceful fallback

    def test_universe_multiple_symbols(self):
        state = {
            "run_mode": "backtest",
            "ticker": "BTC/USDT",
            "universe": ["BTC/USDT", "ETH/USDT"],
            "shared_memory": {
                "backtest": {
                    "window_last_ts_ms": 1700000000000.0,
                    "window_len": 10,
                    "interval_sec": 86400,
                    "timeframe": "1d",
                    "run_id": "bt_67890",
                }
            },
        }
        result = _build_simulation_context(state, "BTC/USDT")
        assert "Universe: BTC/USDT, ETH/USDT" in result
