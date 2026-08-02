"""Tests for concurrent Live paper + Research desk status."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from api import desk_ownership as desk


def _patch_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(desk, "RUNS_DIR", tmp_path)
    monkeypatch.setattr(desk, "PID_FILE", tmp_path / "paper_engine.pid")
    monkeypatch.setattr(desk, "STATUS_FILE", tmp_path / "paper_engine.status.json")
    monkeypatch.setattr(desk, "BACKTESTS_DIR", tmp_path / "backtests")
    monkeypatch.setattr(desk, "LATEST_PAPER_FILE", tmp_path / "latest_paper.txt")
    monkeypatch.setattr(desk, "LATEST_BACKTEST_FILE", tmp_path / "latest_backtest.txt")
    monkeypatch.setattr(desk, "LATEST_RUN_FILE", tmp_path / "latest_run.txt")


def test_desk_idle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_paths(tmp_path, monkeypatch)
    st = desk.desk_status()
    assert st["mode"] == "idle"
    assert st["can_start_paper"] is True
    assert st["can_start_backtest"] is True


def test_dual_mode_when_both_active(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_paths(tmp_path, monkeypatch)
    pid_file = tmp_path / "paper_engine.pid"
    pid_file.write_text("1")
    monkeypatch.setattr(desk, "_pid_alive", lambda _pid: True)
    (tmp_path / "latest_paper.txt").write_text("run-BTC-USDT-1")
    (tmp_path / "paper_engine.status.json").write_text(
        json.dumps({"paper_run_id": "run-BTC-USDT-1"}), encoding="utf-8"
    )
    bt_dir = tmp_path / "backtests" / "bt-abc123"
    bt_dir.mkdir(parents=True)
    (bt_dir / "job.json").write_text(
        json.dumps(
            {"status": "running", "updated_at": 9_999_999_999, "step": 3, "total_steps": 10}
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(desk, "_active_backtests_from_memory", lambda: [])

    st = desk.desk_status()
    assert st["mode"] == "dual"
    assert st["paper_running"] is True
    assert st["active_backtest_id"] == "bt-abc123"
    assert st["can_start_paper"] is True
    assert st["can_start_backtest"] is True


def test_resolve_alias_keeps_lanes_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _patch_paths(tmp_path, monkeypatch)
    (tmp_path / "latest_paper.txt").write_text("run-ETH-USDT-9")
    (tmp_path / "latest_backtest.txt").write_text("bt-zzzz")
    (tmp_path / "latest_run.txt").write_text("bt-should-not-win")
    (tmp_path / "paper_engine.status.json").write_text(
        json.dumps({"paper_run_id": "run-ETH-USDT-9"}), encoding="utf-8"
    )

    assert desk.resolve_alias("latest-paper") == "run-ETH-USDT-9"
    assert desk.resolve_alias("latest") == "run-ETH-USDT-9"
    assert desk.resolve_alias("latest-backtest") == "bt-zzzz"
    assert desk.paper_run_id_from_status() == "run-ETH-USDT-9"
