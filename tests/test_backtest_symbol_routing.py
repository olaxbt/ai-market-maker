"""Tests for per-symbol strategy routing and VCP signal adapter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backtest.symbol_routing import (
    DEFAULT_AGENT_LED_SYMBOLS,
    resolve_agent_led_symbols,
    uses_mixed_routing,
)
from backtest.vcp_signal import (
    bars_window_to_df,
    timeframe_to_scan_tf,
    vcp_result_to_target_weight,
)


def test_resolve_agent_led_defaults():
    led = resolve_agent_led_symbols(universe=["BTC/USDT", "BNB/USDT"])
    assert "BTC/USDT" in led
    assert "BNB/USDT" not in led


def test_resolve_agent_led_env_override(monkeypatch):
    monkeypatch.setenv("AIMM_AGENT_LED_SYMBOLS", "BNB/USDT,XRP/USDT")
    led = resolve_agent_led_symbols()
    assert led == frozenset({"BNB/USDT", "XRP/USDT"})


def test_uses_mixed_routing():
    led = frozenset({"BTC/USDT", "ETH/USDT"})
    assert uses_mixed_routing(led, ["BTC/USDT", "BNB/USDT"])
    assert not uses_mixed_routing(led, ["BTC/USDT", "ETH/USDT"])
    assert not uses_mixed_routing(led, ["BNB/USDT", "XRP/USDT"])


def test_timeframe_to_scan_tf():
    assert timeframe_to_scan_tf("1d") == "1d"
    assert timeframe_to_scan_tf("", interval_sec=86400) == "1d"


def test_bars_window_to_df():
    window = [[1_700_000_000_000, 100, 110, 90, 105, 1000]]
    df = bars_window_to_df(window)
    assert len(df) == 1
    assert float(df["close"].iloc[0]) == 105.0


def test_vcp_result_to_target_weight_strict():
    res = MagicMock(
        error=None,
        passed_relaxed=True,
        passed_strict=True,
        vcp_score=80.0,
        distance_to_pivot_pct=2.0,
    )
    assert vcp_result_to_target_weight(res) == pytest.approx(0.8)


def test_vcp_result_to_target_weight_far_from_pivot():
    res = MagicMock(
        error=None,
        passed_relaxed=True,
        passed_strict=True,
        vcp_score=80.0,
        distance_to_pivot_pct=8.0,
    )
    assert vcp_result_to_target_weight(res) == 0.0


@patch("backtest.engine.build_workflow")
def test_engine_routes_alts_to_vcp(mock_build_wf, tmp_path):
    from backtest.engine import BacktestEngine

    mock_wf = MagicMock()
    mock_build_wf.return_value.compile.return_value = mock_wf
    mock_wf.invoke.return_value = {
        "trade_intent": {"action": "BUY", "confidence": 0.9},
    }

    n = 220
    bars = [
        [1_700_000_000_000 + i * 86_400_000, 100 + i, 101 + i, 99 + i, 100 + i, 10.0]
        for i in range(n)
    ]

    vcp_calls: list[str] = []

    def fake_vcp(symbol, window, **kwargs):
        vcp_calls.append(symbol)
        return 0.4, {"decision": {"action": "BUY", "confidence": 0.4, "stance": "bullish"}}

    with patch("backtest.vcp_signal.vcp_target_weight_from_window", side_effect=fake_vcp):
        engine = BacktestEngine(
            {
                "initial_cash_usd": 10_000,
                "fee_bps": 0,
                "slippage_bps": 0,
                "interval_sec": 86_400,
                "leverage": 1.0,
                "take_profit_pct": 0,
                "stop_loss_pct": 0,
                "timeframe": "1d",
                "export_bundle": False,
                "agent_led_symbols": sorted(DEFAULT_AGENT_LED_SYMBOLS),
            }
        )
        engine.run(
            ticker="BTC/USDT",
            bars_by_symbol={"BTC/USDT": bars, "BNB/USDT": bars},
            run_id="bt_route_test",
            runs_dir=tmp_path,
        )

    assert mock_wf.invoke.call_count > 0
    assert "BNB/USDT" in vcp_calls
    assert "BTC/USDT" not in vcp_calls
