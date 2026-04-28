from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from api.auth_routes import require_user_id
from config.app_settings import load_app_settings
from paper_account import load_or_init_account
from storage.leadpage_db import database_url as _db_url
from storage.leadpage_db import get_or_init_paper_account as _db_get_or_init_paper_account
from storage.leadpage_db import list_paper_trades as _db_list_paper_trades

router = APIRouter(tags=["paper"])

RUNS_DIR = Path(".runs")


def _account_id(uid: int) -> str:
    return f"user-{int(uid)}"


@router.get("/paper/snapshot")
def get_snapshot(request: Request) -> dict[str, Any]:
    uid = require_user_id(request)
    s = load_app_settings()
    if _db_url():
        snap = _db_get_or_init_paper_account(uid, start_usdt=float(s.paper.start_usdt))
        return {"snapshot": snap}
    acct = load_or_init_account(
        runs_dir=RUNS_DIR, account_id=_account_id(uid), start_usdt=float(s.paper.start_usdt)
    )
    return {"snapshot": acct.snapshot(instrument=str(s.paper.instrument))}


@router.get("/paper/trades")
def get_trades(request: Request, limit: int = Query(200, ge=1, le=5000)) -> dict[str, Any]:
    uid = require_user_id(request)
    if _db_url():
        return {"trades": _db_list_paper_trades(uid, limit=int(limit))}
    acct_id = _account_id(uid)
    trades_path = RUNS_DIR / "paper" / f"{acct_id}.trades.jsonl"
    if not trades_path.exists():
        return {"trades": []}
    rows: list[dict[str, Any]] = []
    try:
        for line in trades_path.read_text(encoding="utf-8").splitlines()[-int(limit) :]:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"trades": rows}
