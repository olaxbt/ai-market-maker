"""Tests for evaluation export (index.jsonl + backtest summaries)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from eval_export import build_evaluation_frame, read_backtest_summaries, read_index_jsonl


def test_read_index_jsonl_skips_bad_lines(tmp_path: Path):
    p = tmp_path / "index.jsonl"
    p.write_text(
        '{"run_id":"a","ticker":"BTC/USDT"}\nnot json\n{"run_id":"b"}\n',
        encoding="utf-8",
    )
    rows = read_index_jsonl(p)
    assert len(rows) == 2
    assert rows[0]["run_id"] == "a"
    assert rows[1]["run_id"] == "b"


def test_read_backtest_summaries(tmp_path: Path):
    bt = tmp_path / "backtests" / "bt_1"
    bt.mkdir(parents=True)
    summary = {
        "run_id": "bt_1",
        "steps": 10,
        "trade_count": 2,
        "metrics": {"sharpe": 1.5},
        "benchmark": {"excess_return_pct": 3.0},
    }
    (bt / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    rows = read_backtest_summaries(tmp_path / "backtests")
    assert len(rows) == 1
    assert rows[0]["run_id"] == "bt_1"
    assert "_backtest_dir" in rows[0]


def test_build_evaluation_frame_merges(tmp_path: Path):
    runs = tmp_path / ".runs"
    runs.mkdir()
    (runs / "index.jsonl").write_text(
        json.dumps({"run_id": "live1", "ticker": "ETH/USDT", "is_vetoed": False}) + "\n",
        encoding="utf-8",
    )
    bt = runs / "backtests" / "bt_x"
    bt.mkdir(parents=True)
    (bt / "summary.json").write_text(
        json.dumps({"run_id": "bt_x", "steps": 5, "trade_count": 1, "metrics": {}}),
        encoding="utf-8",
    )
    df = build_evaluation_frame(runs_dir=runs, include_backtests=True)
    assert len(df) == 2
    kinds = set(df["record_kind"].tolist())
    assert kinds == {"index", "backtest"}


def test_build_evaluation_frame_index_only(tmp_path: Path):
    runs = tmp_path / ".runs"
    runs.mkdir()
    (runs / "index.jsonl").write_text(
        json.dumps({"run_id": "x"}) + "\n",
        encoding="utf-8",
    )
    df = build_evaluation_frame(runs_dir=runs, include_backtests=False)
    assert len(df) == 1
    assert df["record_kind"].iloc[0] == "index"


def test_json_normalize_nested_metrics(tmp_path: Path):
    runs = tmp_path / ".runs"
    runs.mkdir()
    bt = runs / "backtests" / "bt_y"
    bt.mkdir(parents=True)
    (bt / "summary.json").write_text(
        json.dumps(
            {
                "run_id": "bt_y",
                "metrics": {"sharpe": 0.5, "max_drawdown_pct": 12.0},
            }
        ),
        encoding="utf-8",
    )
    df = build_evaluation_frame(runs_dir=runs, include_backtests=True)
    assert "metrics.sharpe" in df.columns
    assert float(df["metrics.sharpe"].iloc[0]) == 0.5


def test_main_writes_csv(tmp_path: Path, monkeypatch, capsys):
    runs = tmp_path / ".runs"
    runs.mkdir()
    (runs / "index.jsonl").write_text(
        json.dumps({"run_id": "m1", "ticker": "BTC/USDT"}) + "\n",
        encoding="utf-8",
    )
    out = tmp_path / "out.csv"
    from eval_export import main

    monkeypatch.chdir(tmp_path)
    code = main(
        [
            "--runs-dir",
            str(runs),
            "-o",
            str(out),
            "-f",
            "csv",
        ]
    )
    assert code == 0
    assert out.exists()
    df = pd.read_csv(out)
    assert len(df) == 1
    assert df["record_kind"].iloc[0] == "index"
