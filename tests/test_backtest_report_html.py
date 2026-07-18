"""Tests for iteration decision helper and HTML report."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backtest.iteration_decision import decision_from_iteration
from backtest.report_html import build_backtest_report_html, write_backtest_report_html


def test_decision_from_iteration_nested():
    it = {"decision": {"action": "BUY", "confidence": 0.8}, "trade_intent": {"action": "HOLD"}}
    assert decision_from_iteration(it)["action"] == "BUY"


def test_decision_from_iteration_legacy():
    it = {"trade_intent": {"action": "SELL", "confidence": 0.6}}
    assert decision_from_iteration(it)["action"] == "SELL"


def test_report_html_minimal_run():
    with tempfile.TemporaryDirectory() as tmp:
        run_dir = Path(tmp)
        summary = {
            "run_id": "bt_test",
            "timeframe": "1d",
            "total_bars": 3,
            "initial_cash": 10000,
            "metrics": {
                "sharpe": 1.2,
                "total_pnl_usd": 100,
                "win_rate_pct": 50,
                "total_return_pct": 1.0,
                "max_drawdown_pct": 0.5,
            },
            "benchmark": {"benchmark_symbol": "BTC/USDT"},
        }
        (run_dir / "summary.json").write_text(json.dumps(summary))
        (run_dir / "iterations.jsonl").write_text(
            json.dumps({"bar_index": 0, "decision": {"action": "BUY", "confidence": 0.7}})
            + "\n"
            + json.dumps({"bar_index": 1, "decision": {"action": "HOLD", "confidence": 0.5}})
        )
        (run_dir / "equity_curve.csv").write_text(
            "bar_index,ts_ms,ts_utc,equity,drawdown_pct\n"
            "0,1700000000000,2023-11-14T00:00:00+00:00,10000,0\n"
            "1,1700086400000,2023-11-15T00:00:00+00:00,10100,0\n"
            "2,1700172800000,2023-11-16T00:00:00+00:00,10050,-0.5\n"
        )
        (run_dir / "bars.json").write_text(
            json.dumps(
                {
                    "benchmark_symbol": "BTC/USDT",
                    "fill_model": "signal_on_completed_bars_fill_at_next_open",
                    "benchmark_equity": [
                        {"ts": 1700000000000, "equity": 10000},
                        {"ts": 1700086400000, "equity": 10150},
                        {"ts": 1700172800000, "equity": 9950},
                    ],
                    "bars": [
                        {
                            "ts": 1700000000000,
                            "o": 49500,
                            "h": 50500,
                            "l": 49000,
                            "c": 50000,
                            "v": 1,
                        },
                        {
                            "ts": 1700086400000,
                            "o": 50000,
                            "h": 51500,
                            "l": 49800,
                            "c": 51000,
                            "v": 1,
                        },
                        {
                            "ts": 1700172800000,
                            "o": 51000,
                            "h": 51200,
                            "l": 50500,
                            "c": 50800,
                            "v": 1,
                        },
                        {
                            "ts": 1700259200000,
                            "o": 50800,
                            "h": 52000,
                            "l": 50700,
                            "c": 51500,
                            "v": 1,
                        },
                    ],
                    "ohlcv_by_symbol": {
                        "BTC/USDT": [
                            {
                                "ts": 1700000000000,
                                "o": 49500,
                                "h": 50500,
                                "l": 49000,
                                "c": 50000,
                                "v": 1,
                            },
                            {
                                "ts": 1700086400000,
                                "o": 50000,
                                "h": 51500,
                                "l": 49800,
                                "c": 51000,
                                "v": 1,
                            },
                            {
                                "ts": 1700172800000,
                                "o": 51000,
                                "h": 51200,
                                "l": 50500,
                                "c": 50800,
                                "v": 1,
                            },
                            {
                                "ts": 1700259200000,
                                "o": 50800,
                                "h": 52000,
                                "l": 50700,
                                "c": 51500,
                                "v": 1,
                            },
                        ],
                    },
                }
            )
        )
        (run_dir / "trades_record.csv").write_text(
            "trade_id,symbol,side,entry_price,exit_price,pnl_usd,holding_bars,exit_reason,entry_bar_index,exit_bar_index\n"
            "1,BTC/USDT,long,50000,51000,100,2,take_profit,1,3\n"
        )
        html = build_backtest_report_html(run_dir)
        assert "Executive Summary" in html
        assert "Chart" in html or "equityChart" in html
        assert "BTC/USDT" in html
        assert "bt_test" in html
        assert "Fill Quality" in html
        out = write_backtest_report_html(run_dir)
        assert out.is_file()
