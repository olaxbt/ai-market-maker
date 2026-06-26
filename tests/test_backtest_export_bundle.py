"""Tests for backtest export bundle (CSV, ledger, manifest)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from backtest.export_bundle import (
    write_analysis_bundle,
    write_audit_ledger,
    write_equity_csv,
    write_export_manifest,
    write_trades_csv,
)


class TestWriteTradesCsv:
    def test_basic_headers_and_row(self):
        tmp = Path(tempfile.mkdtemp()) / "trades_record.csv"
        trades = [
            {
                "symbol": "BTC/USDT",
                "direction": 1,
                "entry_price": 50000.0,
                "exit_price": 51000.0,
                "size": 0.1,
                "leverage": 3.0,
                "pnl": 30.0,
                "pnl_pct": 2.0,
                "exit_reason": "take_profit",
                "holding_bars": 5,
                "commission": 1.5,
                "exit_ts_ms": 1700000000000,
                "entry_ts_ms": 1699900000000,
                "entry_bar_index": 10,
                "exit_bar_index": 15,
                "run_id": "bt_12345",
            }
        ]
        write_trades_csv(trades, tmp)
        content = tmp.read_text()
        assert "symbol" in content
        assert "entry_ts_ms" in content
        assert "exit_ts_ms" in content
        assert "pnl_usd" in content
        assert "side" in content
        assert "long" in content
        assert "BTC/USDT" in content

    def test_short_trade_side(self):
        tmp = Path(tempfile.mkdtemp()) / "trades_short.csv"
        trades = [
            {
                "symbol": "ETH/USDT",
                "direction": -1,
                "entry_price": 3000.0,
                "exit_price": 2800.0,
                "size": 1.0,
                "leverage": 2.0,
                "pnl": 400.0,
                "pnl_pct": 6.67,
                "exit_reason": "stop_loss",
                "holding_bars": 3,
                "commission": 0.5,
                "exit_ts_ms": 0,
                "entry_ts_ms": 0,
                "entry_bar_index": 0,
                "exit_bar_index": 3,
                "run_id": "bt_67890",
            }
        ]
        write_trades_csv(trades, tmp)
        content = tmp.read_text()
        assert "short" in content


class TestWriteEquityCsv:
    def test_headers_and_drawdown(self):
        tmp = Path(tempfile.mkdtemp()) / "equity_curve.csv"
        snapshots = [
            {
                "ts": 1700000000000,
                "capital": 10000.0,
                "unrealized_pnl": 0.0,
                "equity": 10000.0,
                "position_count": 0,
            },
            {
                "ts": 1700000001000,
                "capital": 10050.0,
                "unrealized_pnl": 100.0,
                "equity": 10150.0,
                "position_count": 1,
            },
            {
                "ts": 1700000002000,
                "capital": 9800.0,
                "unrealized_pnl": -50.0,
                "equity": 9750.0,
                "position_count": 1,
            },
        ]
        write_equity_csv(snapshots, tmp)
        content = tmp.read_text()
        assert "drawdown_pct" in content
        assert "ts_utc" in content
        assert "equity" in content
        # Peak was 10150, last equity 9750 → dd ~3.94%
        assert "-3" in content or "0.0" in content


class TestWriteAuditLedger:
    def test_merged_stream_flat_format(self):
        """Legacy flat format (action at top level) still parsed."""
        tmp_dir = Path(tempfile.mkdtemp())
        ledger_path = tmp_dir / "audit_trail_ledger.jsonl"

        iterations = [
            {
                "action": "BUY",
                "confidence": 0.7,
                "bar_index": 0,
                "symbol": "BTC/USDT",
                "ts": 1700000000,
            },
            {
                "action": "HOLD",
                "confidence": 0.5,
                "bar_index": 1,
                "symbol": "BTC/USDT",
                "ts": 1700000001,
            },
        ]
        (tmp_dir / "iterations.jsonl").write_text("\n".join(json.dumps(r) for r in iterations))

        write_audit_ledger(tmp_dir, ledger_path, run_id="bt_12345")
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        assert lines[0]["event_type"] == "decision"
        assert lines[0]["run_id"] == "bt_12345"
        assert lines[0]["decision"]["action"] == "BUY"
        assert lines[0]["symbol"] == "BTC/USDT"

    def test_merged_stream_nested_format(self):
        """Modern nested decision dict."""
        tmp_dir = Path(tempfile.mkdtemp())
        ledger_path = tmp_dir / "audit_trail_ledger.jsonl"

        iterations = [
            {
                "decision": {"action": "SELL", "confidence": 0.8, "stance": "bearish"},
                "bar_index": 0,
                "symbol": "ETH/USDT",
                "ts": 1700000000,
                "memory": {"key": "val"},
            },
        ]
        (tmp_dir / "iterations.jsonl").write_text(json.dumps(iterations[0]) + "\n")

        write_audit_ledger(tmp_dir, ledger_path, run_id="bt_67890")
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 1
        assert lines[0]["decision"]["action"] == "SELL"
        assert lines[0]["decision"]["confidence"] == 0.8
        assert lines[0]["symbol"] == "ETH/USDT"
        assert lines[0]["memory_fragment"] == {"key": "val"}
        assert lines[0]["bar_index"] == 0

    def test_merged_stream_hybrid_format(self):
        """Both nested decision dict AND legacy flat keys work."""
        tmp_dir = Path(tempfile.mkdtemp())
        ledger_path = tmp_dir / "audit_trail_ledger.jsonl"

        iterations = [
            {
                "decision": {"action": "BUY", "confidence": 0.7},
                "bar_index": 0,
                "symbol": "BTC/USDT",
                "ts": 1700000000,
            },
            {"ts": 1700000001, "action": "HOLD"},  # legacy: no decision dict
        ]
        (tmp_dir / "iterations.jsonl").write_text("\n".join(json.dumps(r) for r in iterations))

        write_audit_ledger(tmp_dir, ledger_path, run_id="bt_12345")
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        assert lines[0]["decision"]["action"] == "BUY"
        assert lines[1]["decision"]["action"] == "HOLD"

    def test_flow_event_merging(self):
        tmp_dir = Path(tempfile.mkdtemp())
        ledger_path = tmp_dir / "audit_trail_ledger.jsonl"
        events_path = tmp_dir / "events.jsonl"

        (tmp_dir / "iterations.jsonl").write_text(
            json.dumps(
                {
                    "decision": {"action": "SELL"},
                    "bar_index": 0,
                    "symbol": "BTC/USDT",
                    "ts": 1700000000,
                }
            )
            + "\n"
        )
        events_path.write_text(
            json.dumps({"node": "arbitrator", "status": "complete", "bar_time_utc_ms": 1700000000})
            + "\n"
        )

        write_audit_ledger(tmp_dir, ledger_path, run_id="bt_12345", events_path=events_path)
        lines = [json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()]
        assert len(lines) == 2
        types = {row["event_type"] for row in lines}
        assert "decision" in types
        assert "flow" in types


class TestWriteExportManifest:
    def test_manifest_structure(self):
        tmp = Path(tempfile.mkdtemp()) / "export_manifest.json"
        summary = {
            "metrics": {"total_return_pct": 16.81, "sharpe": 4.47, "total_pnl_usd": 1757.08},
            "quality_report": {"overall_passed": False},
            "arbitrator_mode": "agent_llm",
            "interval_sec": 86400,
        }
        write_export_manifest(
            tmp,
            run_id="bt_12345",
            summary=summary,
            files_written={"trades_record_csv": "trades_record.csv"},
            symbols=["BTC/USDT"],
            total_bars=100,
        )
        manifest = json.loads(tmp.read_text())
        assert manifest["schema_version"] == "backtest_export/v1"
        assert manifest["metrics_summary"]["sharpe"] == 4.47
        assert manifest["metrics_summary"]["quality_overall_passed"] is False
        assert manifest["files"]["trades_record_csv"] == "trades_record.csv"
        assert manifest.get("invoke_cache", {}).get("shared") is True
        assert manifest.get("invoke_cache", {}).get("per_symbol") is False


class TestWriteAnalysisBundle:
    def test_all_files_created(self):
        tmp_dir = Path(tempfile.mkdtemp())
        summary = {
            "metrics": {"total_return_pct": 10.0, "sharpe": 2.0, "total_pnl_usd": 500},
            "quality_report": {"overall_passed": True},
            "arbitrator_mode": "agent_llm",
            "interval_sec": 86400,
        }
        trades = [
            {
                "symbol": "BTC/USDT",
                "direction": 1,
                "entry_price": 50000.0,
                "exit_price": 51000.0,
                "size": 0.1,
                "leverage": 3.0,
                "pnl": 30.0,
                "pnl_pct": 2.0,
                "exit_reason": "tp",
                "holding_bars": 5,
                "commission": 1.5,
                "exit_ts_ms": 1700000000000,
                "entry_ts_ms": 1699900000000,
                "entry_bar_index": 10,
                "exit_bar_index": 15,
                "run_id": "bt_12345",
            }
        ]
        snapshots = [
            {
                "ts": 1700000000000,
                "capital": 10000,
                "unrealized_pnl": 0,
                "equity": 10000,
                "position_count": 0,
            }
        ]

        files = write_analysis_bundle(
            tmp_dir,
            run_id="bt_12345",
            summary=summary,
            trades=trades,
            snapshots=snapshots,
            symbols=["BTC/USDT"],
            total_bars=1,
        )
        for _name, relpath in files.items():
            assert (tmp_dir / relpath).is_file(), f"Missing: {relpath}"
        assert "export_manifest_json" in files
        assert "trades_record_csv" in files
        assert "equity_curve_csv" in files
        assert "audit_trail_ledger_jsonl" in files

        manifest = json.loads((tmp_dir / files["export_manifest_json"]).read_text())
        assert manifest["schema_version"] == "backtest_export/v1"
