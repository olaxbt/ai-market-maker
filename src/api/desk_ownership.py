"""Live paper + Research backtest desk status."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from config.runs_paths import runs_dir as _resolved_runs_dir

RUNS_DIR = _resolved_runs_dir()
PID_FILE = RUNS_DIR / "paper_engine.pid"
STATUS_FILE = RUNS_DIR / "paper_engine.status.json"
BACKTESTS_DIR = RUNS_DIR / "backtests"
LATEST_PAPER_FILE = RUNS_DIR / "latest_paper.txt"
LATEST_BACKTEST_FILE = RUNS_DIR / "latest_backtest.txt"
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def paper_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
    except Exception:
        return None
    if not _pid_alive(pid):
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass
        return None
    return pid


def paper_is_running() -> bool:
    return paper_pid() is not None


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _job_stale_sec() -> int:
    return max(60, int(os.environ.get("BACKTEST_JOB_STALE_SEC", "240")))


def _active_backtests_from_memory() -> list[dict[str, Any]]:
    try:
        from api.backtest_routes import BACKTEST_JOBS
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    for rid, job in list(BACKTEST_JOBS.items()):
        if not isinstance(job, dict):
            continue
        if str(job.get("status") or "") not in ("queued", "running"):
            continue
        out.append(
            {
                "run_id": str(rid),
                "status": str(job.get("status")),
                "step": job.get("step"),
                "total_steps": job.get("total_steps"),
                "source": "memory",
            }
        )
    return out


def _active_backtests_from_disk() -> list[dict[str, Any]]:
    if not BACKTESTS_DIR.is_dir():
        return []
    stale_after = _job_stale_sec()
    now = int(time.time())
    out: list[dict[str, Any]] = []
    try:
        children = list(BACKTESTS_DIR.iterdir())
    except Exception:
        return []
    for child in children:
        if not child.is_dir():
            continue
        job = _read_json(child / "job.json")
        if not job:
            continue
        status = str(job.get("status") or "")
        if status not in ("queued", "running"):
            continue
        updated = job.get("updated_at")
        try:
            updated_i = (
                int(updated) if updated is not None else int((child / "job.json").stat().st_mtime)
            )
        except Exception:
            updated_i = now
        if now - updated_i > stale_after:
            continue
        out.append(
            {
                "run_id": child.name,
                "status": status,
                "step": job.get("step"),
                "total_steps": job.get("total_steps"),
                "source": "disk",
            }
        )
    return out


def active_backtest_jobs() -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in _active_backtests_from_memory() + _active_backtests_from_disk():
        rid = str(row.get("run_id") or "")
        if rid:
            by_id[rid] = row
    return list(by_id.values())


def active_backtest_id() -> str | None:
    jobs = active_backtest_jobs()
    if not jobs:
        return None
    return str(jobs[0].get("run_id") or "") or None


def read_text_id(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        v = path.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    return v or None


def write_text_id(path: Path, run_id: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(run_id).strip(), encoding="utf-8")
    except Exception:
        pass


def _is_backtest_id(run_id: str | None) -> bool:
    if not run_id:
        return False
    return run_id.lower().startswith("bt")


def paper_run_id_from_status() -> str | None:
    st = _read_json(STATUS_FILE) or {}
    for key in ("paper_run_id", "current_run_id", "run_id"):
        v = st.get(key)
        if isinstance(v, str) and v.strip() and not _is_backtest_id(v.strip()):
            return v.strip()
    for path in (LATEST_PAPER_FILE, LATEST_RUN_FILE):
        rid = read_text_id(path)
        if rid and not _is_backtest_id(rid):
            return rid
    return None


def resolve_alias(run_id: str) -> str | None:
    """Map stream aliases to a concrete run id (or None if unknown)."""
    rid = (run_id or "").strip()
    if not rid:
        return None
    lower = rid.lower()
    if lower in ("latest-paper", "latest_paper", "paper"):
        return paper_run_id_from_status() or read_text_id(LATEST_PAPER_FILE)
    if lower in ("latest-backtest", "latest_backtest", "backtest"):
        return active_backtest_id() or read_text_id(LATEST_BACKTEST_FILE)
    if lower == "latest":
        # latest alias → paper run, not bt-*
        paper = paper_run_id_from_status() or read_text_id(LATEST_PAPER_FILE)
        if paper:
            return paper
        legacy = read_text_id(LATEST_RUN_FILE)
        if legacy and not _is_backtest_id(legacy):
            return legacy
        return None
    return rid


def desk_status() -> dict[str, Any]:
    paper_on = paper_is_running()
    jobs = active_backtest_jobs()
    bt_id = str(jobs[0]["run_id"]) if jobs else None
    bt_on = bt_id is not None
    paper_rid = paper_run_id_from_status() if paper_on else None
    lanes_active = int(paper_on) + int(bt_on)
    if lanes_active == 2:
        mode = "dual"
        message = (
            "Live book and Research backtest are both running — "
            "Live desk shows paper thoughts; Research shows the backtest report/timeline."
        )
    elif paper_on:
        mode = "live"
        message = "Live session running. You can start a Research backtest to fine-tune agents in parallel."
    elif bt_on:
        mode = "research"
        message = (
            "Research backtest running. Live book stays available — start a Live session anytime."
        )
    else:
        mode = "idle"
        message = "No active lanes. Start a Live session and/or a Research backtest."

    paper_st: dict[str, Any] = {}
    if STATUS_FILE.is_file():
        try:
            raw = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                paper_st = raw
        except Exception:
            paper_st = {}

    phase = paper_st.get("phase") if paper_on else None
    if paper_on and not phase:
        phase = "scanning" if paper_rid else "waiting"

    return {
        "mode": mode,
        "paper_running": paper_on,
        "paper_run_id": paper_rid,
        "paper_ticker": paper_st.get("ticker") if paper_on else None,
        "paper_interval_sec": paper_st.get("interval_sec") if paper_on else None,
        "paper_started_at": paper_st.get("started_at") if paper_on else None,
        "paper_phase": phase,
        "paper_scan_iteration": paper_st.get("scan_iteration") if paper_on else None,
        "paper_last_scan_started_at": paper_st.get("last_scan_started_at") if paper_on else None,
        "paper_last_scan_finished_at": paper_st.get("last_scan_finished_at") if paper_on else None,
        "paper_next_scan_at": paper_st.get("next_scan_at") if paper_on else None,
        "paper_updated_at": paper_st.get("updated_at") if paper_on else None,
        "active_backtest_id": bt_id,
        "active_backtests": jobs,
        "latest_paper_id": read_text_id(LATEST_PAPER_FILE),
        "latest_backtest_id": read_text_id(LATEST_BACKTEST_FILE),
        "can_start_paper": True,
        "can_start_backtest": True,
        "message": message,
        # deprecated; use mode
        "owner": "dual"
        if lanes_active == 2
        else ("paper" if paper_on else ("backtest" if bt_on else "idle")),
    }
