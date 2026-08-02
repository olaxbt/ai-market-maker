"""Live paper engine: start/stop loop + desk/book status."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.desk_ownership import desk_status, paper_run_id_from_status
from config.runs_paths import runs_dir as _resolved_runs_dir

router = APIRouter(prefix="/engine", tags=["engine"])

RUNS_DIR = _resolved_runs_dir()
PID_FILE = RUNS_DIR / "paper_engine.pid"
STATUS_FILE = RUNS_DIR / "paper_engine.status.json"
REPO_ROOT = Path(__file__).resolve().parents[2]


class PaperStartRequest(BaseModel):
    ticker: str = Field("BTC/USDT", min_length=3, max_length=64)
    interval_sec: int = Field(900, ge=300, le=3600)


def _read_status() -> dict[str, Any]:
    if STATUS_FILE.exists():
        try:
            return json.loads(STATUS_FILE.read_text())
        except Exception:
            pass
    return {}


def _write_status(data: dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    STATUS_FILE.write_text(json.dumps(data, indent=2))


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _current_pid() -> int | None:
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


@router.get("/desk")
def get_desk_status() -> dict[str, Any]:
    return desk_status()


@router.get("/paper/status")
def paper_status() -> dict[str, Any]:
    pid = _current_pid()
    st = _read_status()
    paper_rid = paper_run_id_from_status() if pid is not None else None
    desk = desk_status()
    phase = st.get("phase") if pid is not None else None
    if pid is not None and not phase:
        phase = "scanning" if paper_rid else "waiting"
    return {
        "running": pid is not None,
        "pid": pid,
        "ticker": st.get("ticker"),
        "interval_sec": st.get("interval_sec"),
        "started_at": st.get("started_at"),
        "phase": phase,
        "scan_iteration": st.get("scan_iteration"),
        "last_scan_started_at": st.get("last_scan_started_at"),
        "last_scan_finished_at": st.get("last_scan_finished_at"),
        "next_scan_at": st.get("next_scan_at") if pid is not None else None,
        "updated_at": st.get("updated_at") if pid is not None else None,
        "latest_run_id": paper_rid,
        "paper_run_id": paper_rid,
        "mode": "paper",
        "desk_mode": desk.get("mode"),
        "active_backtest_id": desk.get("active_backtest_id"),
        "desk_message": desk.get("message"),
    }


@router.post("/paper/start")
def paper_start(req: PaperStartRequest) -> dict[str, Any]:
    existing = _current_pid()
    if existing is not None:
        st = paper_status()
        st["message"] = "Paper loop already running"
        return st

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    script = REPO_ROOT / "scripts" / "run_paper_loop.py"
    if not script.is_file():
        raise HTTPException(status_code=500, detail=f"missing script: {script}")

    env = os.environ.copy()
    env["MODE"] = "paper"
    env["TICKER"] = req.ticker.strip()
    env["STRATEGY_INTERVAL_SEC"] = str(req.interval_sec)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    log_path = RUNS_DIR / "paper_engine.log"
    log_f = open(log_path, "a", encoding="utf-8")
    try:
        proc = subprocess.Popen(
            [
                sys.executable,
                str(script),
                "--ticker",
                req.ticker.strip(),
                "--interval-sec",
                str(req.interval_sec),
            ],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=log_f,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    except Exception as e:
        log_f.close()
        raise HTTPException(status_code=500, detail=f"failed to start paper loop: {e}") from e

    PID_FILE.write_text(str(proc.pid))
    now = int(time.time())
    started = {
        "ticker": req.ticker.strip(),
        "interval_sec": req.interval_sec,
        "started_at": now,
        "pid": proc.pid,
        "phase": "scanning",
        "scan_iteration": 0,
        "next_scan_at": None,
        "updated_at": now,
    }
    _write_status(started)
    return {"running": True, **started, "log": str(log_path)}


@router.post("/paper/stop")
def paper_stop() -> dict[str, Any]:
    pid = _current_pid()
    if pid is None:
        return {"running": False, "message": "Paper loop was not running"}
    try:
        os.killpg(pid, signal.SIGTERM)
    except Exception:
        try:
            os.kill(pid, signal.SIGTERM)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"failed to stop pid {pid}: {e}") from e

    for _ in range(20):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    if _pid_alive(pid):
        try:
            os.killpg(pid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass

    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    st = _read_status()
    st["stopped_at"] = int(time.time())
    st["running"] = False
    _write_status(st)
    return {"running": False, "stopped_pid": pid}


class PaperBookResetRequest(BaseModel):
    start_usdt: float | None = Field(
        None, gt=0, description="Optional override; default from app settings."
    )


@router.get("/paper/book")
def paper_book() -> dict[str, Any]:
    """Local paper book (account_id=default, no auth)."""
    from config.app_settings import load_app_settings
    from paper_account import load_or_init_account

    s = load_app_settings()
    start = float(s.paper.start_usdt)
    acct = load_or_init_account(runs_dir=RUNS_DIR, account_id="default", start_usdt=start)
    snap = acct.snapshot(instrument=str(s.paper.instrument))
    free_cash = float(snap.get("cash_usdt") or 0)
    margin_locked = 0.0
    for p in snap.get("perp_positions") or []:
        try:
            margin_locked += float(p.get("margin_locked_usdt") or 0.0)
        except (TypeError, ValueError):
            continue
    equity = free_cash + margin_locked
    return {
        "account_id": "default",
        "start_usdt": start,
        "cash_usdt": free_cash,
        "free_cash_usdt": free_cash,
        "margin_locked_usdt": margin_locked,
        "equity_usdt": equity,
        "positions": list(snap.get("positions") or []),
        "note": "equity_usdt = free cash + margin locked. Free cash alone looks tiny while perps are open.",
    }


@router.post("/paper/book/reset")
def paper_book_reset(req: PaperBookResetRequest | None = None) -> dict[str, Any]:
    """Reset local default paper book to start_usdt (clears positions)."""
    from config.app_settings import load_app_settings
    from paper_account import PaperAccount, save_account

    s = load_app_settings()
    start = float(req.start_usdt) if req and req.start_usdt else float(s.paper.start_usdt)
    acct = PaperAccount(account_id="default", cash_usdt=start, updated_ts=int(time.time()))
    save_account(runs_dir=RUNS_DIR, account=acct)
    trades = RUNS_DIR / "paper" / "default.trades.jsonl"
    try:
        if trades.exists():
            trades.unlink()
    except Exception:
        pass
    return {
        "ok": True,
        "account_id": "default",
        "start_usdt": start,
        "cash_usdt": start,
        "positions": [],
    }
