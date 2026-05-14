"""Operator endpoints ("control plane").

These routes are intended for the Control Center UI and ChatOps.
They must be safe by default, explicit, and easy to reason about.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.backtest_routes import (
    QuickBacktestRequest,
    _execute_quick_backtest,
    post_quick_backtest_async,
)
from storage.leadpage_db import engine as leadpage_engine
from storage.leadpage_db import insert_local_backtest_result_if_missing

RUNS_DIR = Path(".runs")
BACKTESTS_DIR = RUNS_DIR / "backtests"

router = APIRouter(prefix="/ops", tags=["ops"])


def _now() -> int:
    return int(time.time())


@router.get("/selftest")
def get_selftest() -> dict[str, Any]:
    """Lightweight readiness check for operators.

    - verifies `.runs/` is writable
    - reports DB connectivity (if configured)
    """

    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    test_file = RUNS_DIR / ".ops_write_test"
    try:
        test_file.write_text(f"{_now()}\n", encoding="utf-8")
        test_file.unlink(missing_ok=True)
        runs_ok = True
        runs_error = None
    except Exception as e:
        runs_ok = False
        runs_error = str(e)

    eng = leadpage_engine()
    db_configured = bool((os.getenv("DATABASE_URL") or "").strip())
    db_ok = False
    db_error = None
    if eng is None:
        db_ok = False
        db_error = None if not db_configured else "engine_unavailable"
    else:
        try:
            with eng.connect() as conn:
                conn.exec_driver_sql("SELECT 1")
            db_ok = True
        except Exception as e:
            db_ok = False
            db_error = str(e)

    ok = runs_ok and (db_ok or not db_configured)
    return {
        "ok": ok,
        "runs": {"ok": runs_ok, "error": runs_error},
        "db": {"configured": db_configured, "ok": db_ok, "error": db_error},
    }


class OpsBacktestRequest(BaseModel):
    ticker: str = Field("BTC/USDT", min_length=3)
    n_bars: int = Field(300, ge=20, le=100_000)
    interval_sec: int = Field(3600, ge=60, le=86_400)
    max_steps: int | None = Field(None, ge=1)
    seed: int | None = Field(None, ge=0)
    fee_bps: float = Field(10.0, ge=0, le=500)
    initial_cash: float = Field(1000.0, gt=0)


@router.post("/backtests/quick")
def post_ops_quick_backtest(req: OpsBacktestRequest) -> dict[str, Any]:
    """Run a quick backtest and return the same shape as `/backtests/quick`."""

    q = QuickBacktestRequest(
        ticker=req.ticker,
        n_bars=req.n_bars,
        interval_sec=req.interval_sec,
        max_steps=req.max_steps,
        seed=req.seed,
        fee_bps=req.fee_bps,
        initial_cash=req.initial_cash,
    )
    return _execute_quick_backtest(q)


@router.post("/backtests/quick/async")
def post_ops_quick_backtest_async(req: OpsBacktestRequest) -> dict[str, Any]:
    """Run a quick backtest asynchronously and return a poll handle for progress."""
    q = QuickBacktestRequest(
        ticker=req.ticker,
        n_bars=req.n_bars,
        interval_sec=req.interval_sec,
        max_steps=req.max_steps,
        seed=req.seed,
        fee_bps=req.fee_bps,
        initial_cash=req.initial_cash,
    )
    return post_quick_backtest_async(q)


class OpsPublishBacktestRequest(BaseModel):
    run_id: str = Field(..., min_length=3)
    confirm: bool = Field(False)


@router.post("/publish/backtest")
def post_ops_publish_backtest(req: OpsPublishBacktestRequest) -> dict[str, Any]:
    """Publish a local backtest summary into the leaderboard DB as provider=`local`.

    This is intentionally *not* the public `/leadpage/external_result` path.
    It is meant for operators running the stack locally or in a trusted environment.
    """

    run_id = (req.run_id or "").strip()
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirm_required",
                "hint": "Set confirm=true to publish a local backtest to provider=local.",
            },
        )

    summary_path = BACKTESTS_DIR / run_id / "summary.json"
    if not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "run_id": run_id, "path": str(summary_path)},
        )

    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_summary", "run_id": run_id, "detail": str(e)},
        ) from e

    try:
        inserted = insert_local_backtest_result_if_missing(summary=summary)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": "publish_failed", "detail": str(e)},
        ) from e

    return {"ok": True, "inserted": bool(inserted), "provider": "local", "run_id": run_id}
