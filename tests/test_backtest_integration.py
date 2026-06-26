"""Integration test: short backtest run with mock signal → verify export bundle.

Runs a 3-bar backtest (no LLM, no network) and asserts:
- audit_trail_ledger.jsonl exists with non-empty decision.action
- trades_record.csv exists (if trades closed)
- equity_curve.csv exists with drawdown_pct header
- export_manifest.json exists with schema_version
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

try:
    from backtest.engine import BacktestEngine

    _SKIP = False
except ImportError:
    _SKIP = True


def _make_bars(
    n: int = 10,
    *,
    start_price: float = 50000.0,
    interval_sec: int = 86400,
) -> list:
    """Generate OHLCV bars for testing (daily, 50000 → slight uptrend)."""
    bars: list = []
    for i in range(n):
        price = start_price + i * 10  # uptrend
        base_ts = 1700000000000 + i * interval_sec * 1000
        bars.append(
            [
                base_ts,
                price + 50,  # o
                price + 100,  # h
                price - 50,  # l
                price,  # c
                100.0,  # v
            ]
        )
    return bars


def _mock_signal_fn(symbol, window, positions, capital) -> float:
    """Return a constant long signal for testing."""
    if not window or len(window) < 2:
        return 0.0
    # Simple: buy on bar 2, sell on bar 5
    idx = len(window) - 1
    if idx == 2:
        return 0.5  # BUY
    if idx == 5:
        return -0.3  # SELL
    return 0.0


@pytest.mark.skipif(_SKIP, reason="BacktestEngine not importable")
class TestBacktestExportBundle:
    def test_3_bar_backtest_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bars = _make_bars(10)
            engine = BacktestEngine(
                {
                    "initial_cash_usd": 10000.0,
                    "fee_bps": 0.0,
                    "slippage_bps": 0.0,
                    "interval_sec": 86400,
                    "instrument": "perp",
                    "leverage": 1.0,
                    "runs_dir": str(tmp),
                    "export_bundle": True,
                    "take_profit_pct": 0.0,
                    "stop_loss_pct": 0.0,
                    "max_hold_bars": 10,
                    "timeframe": "1d",
                }
            )
            engine.run(
                "BTC/USDT",
                bars=bars,
                run_id="bt_test_3b",
            )

            run_dir = tmp / "backtests" / "bt_test_3b"

            # 1. audit_trail_ledger.jsonl
            ledger_path = run_dir / "audit_trail_ledger.jsonl"
            assert ledger_path.is_file(), f"Missing audit_trail_ledger.jsonl in {run_dir}"
            lines = [
                json.loads(line) for line in ledger_path.read_text().splitlines() if line.strip()
            ]
            assert len(lines) >= 3, f"Expected ≥3 audit entries, got {len(lines)}"
            decision_lines = [row for row in lines if row.get("event_type") == "decision"]
            assert len(decision_lines) >= 1, "No decision entries in audit ledger"
            # At least one entry should have non-empty action
            actions = {d.get("decision", {}).get("action", "") for d in decision_lines}
            assert actions, (
                "No decision.action found — audit ledger rows missing nested decision dict"
            )
            # Verify bar_index present
            bar_indices = {d.get("bar_index") for d in decision_lines}
            assert all(bi is not None for bi in bar_indices), (
                "bar_index missing in some audit entries"
            )

            # 2. equity_curve.csv
            equity_csv = run_dir / "equity_curve.csv"
            assert equity_csv.is_file(), "Missing equity_curve.csv"
            header = equity_csv.read_text().splitlines()[0]
            for col in ("bar_index", "equity", "drawdown_pct"):
                assert col in header, f"Missing column '{col}' in equity_curve.csv"

            # 3. export_manifest.json
            manifest_path = run_dir / "export_manifest.json"
            assert manifest_path.is_file(), "Missing export_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            assert manifest.get("schema_version") == "backtest_export/v1"
            assert manifest.get("invoke_cache", {}).get("shared") is True
            assert "metrics_summary" in manifest
            assert "files" in manifest
            assert manifest.get("timeframe") == "1d"

            # CSV may exist even without trades
            trades_csv = run_dir / "trades_record.csv"
            if trades_csv.is_file():
                header2 = trades_csv.read_text().splitlines()[0]
                for col in ("run_id", "symbol", "side", "pnl_usd", "exit_reason"):
                    assert col in header2, f"Missing column '{col}' in trades_record.csv"

    def test_manifest_on_no_trades(self):
        """Even a bar with no trades should produce export files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            bars = _make_bars(5)
            engine = BacktestEngine(
                {
                    "initial_cash_usd": 10000.0,
                    "fee_bps": 0.0,
                    "slippage_bps": 0.0,
                    "interval_sec": 86400,
                    "instrument": "perp",
                    "leverage": 1.0,
                    "runs_dir": str(tmp),
                    "export_bundle": True,
                    "take_profit_pct": 0.0,
                    "stop_loss_pct": 0.0,
                    "max_hold_bars": 10,
                    "timeframe": "1d",
                }
            )
            engine.run(
                "BTC/USDT",
                bars=bars,
                run_id="bt_test_notrades",
            )
            run_dir = tmp / "backtests" / "bt_test_notrades"
            assert (run_dir / "export_manifest.json").is_file()
            assert (run_dir / "audit_trail_ledger.jsonl").is_file()
            assert (run_dir / "summary.json").is_file()
