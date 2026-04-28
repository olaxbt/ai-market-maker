from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth_routes import require_user_id
from config.app_settings import load_app_settings
from paper_account import (
    append_trade,
    apply_perp_fill,
    apply_spot_fill,
    load_or_init_account,
    save_account,
)
from storage.leadpage_db import (
    append_paper_trade as _db_append_paper_trade,
)
from storage.leadpage_db import (
    database_url as _db_url,
)
from storage.leadpage_db import (
    get_copy_setting,
    get_signal,
    inbox_items,
    list_executions,
    mark_inbox_read,
    record_execution,
    upsert_copy_setting,
)
from storage.leadpage_db import (
    get_or_init_paper_account as _db_get_or_init_paper_account,
)
from storage.leadpage_db import (
    save_paper_account as _db_save_paper_account,
)

router = APIRouter(tags=["copy"])

RUNS_DIR = Path(".runs")


class UpsertSettingRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=80)
    enabled: bool = Field(False)
    auto_execute: bool = Field(False, description="If true, worker may auto-execute ops intents.")
    instrument: Literal["spot", "perp"] = Field("spot")
    max_notional_usdt: float | None = Field(None, gt=0)


@router.get("/copy/settings")
def get_setting(
    request: Request, provider: str = Query(..., min_length=2, max_length=80)
) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(status_code=400, detail="Copy requires DATABASE_URL (Postgres mode).")
    uid = require_user_id(request)
    s = get_copy_setting(uid, provider)
    return {"setting": s}


@router.post("/copy/settings")
def post_setting(request: Request, req: UpsertSettingRequest) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(status_code=400, detail="Copy requires DATABASE_URL (Postgres mode).")
    uid = require_user_id(request)
    s = upsert_copy_setting(
        user_id=uid,
        provider=req.provider,
        enabled=bool(req.enabled),
        auto_execute=bool(req.auto_execute),
        instrument=req.instrument,
        max_notional_usdt=req.max_notional_usdt,
    )
    return {"ok": True, "setting": s}


class ExecuteInboxRequest(BaseModel):
    inbox_id: int = Field(..., ge=1)


def _intent_from_signal_meta(meta: dict[str, Any]) -> dict[str, Any] | None:
    it = meta.get("intent") if isinstance(meta.get("intent"), dict) else None
    return it if isinstance(it, dict) else None


def execute_inbox_item(*, user_id: int, inbox_id: int) -> dict[str, Any]:
    """Pure helper for worker/UI to execute without a FastAPI Request."""
    if not _db_url():
        raise RuntimeError("DATABASE_URL is not set")
    uid = int(user_id)

    rows = inbox_items(uid, limit=5000)
    it = next((r for r in rows if int(r.get("id") or 0) == int(inbox_id)), None)
    if not it:
        raise HTTPException(status_code=404, detail="inbox item not found")

    signal_id = int(it.get("signal_id") or 0)
    provider = str(it.get("provider") or "")
    sig = get_signal(signal_id)
    if not sig:
        raise HTTPException(status_code=404, detail="signal not found")
    if str(sig.get("kind") or "") != "ops":
        raise HTTPException(status_code=400, detail="only ops signals are executable")

    meta = sig.get("meta") if isinstance(sig.get("meta"), dict) else {}
    intent = _intent_from_signal_meta(meta)
    if not intent:
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="rejected",
            detail="missing meta.intent",
            trade=None,
        )
        return {"ok": False, "execution": ex}

    setting = get_copy_setting(uid, provider) or {
        "enabled": True,
        "auto_execute": False,
        "instrument": "spot",
        "max_notional_usdt": None,
    }
    if not bool(setting.get("enabled", True)):
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="rejected",
            detail="copy disabled for provider",
            trade=None,
        )
        return {"ok": False, "execution": ex}

    instrument = str(intent.get("instrument") or setting.get("instrument") or "spot").lower()
    if instrument not in {"spot", "perp"}:
        instrument = "spot"
    symbol = str(intent.get("symbol") or intent.get("ticker") or sig.get("ticker") or "").strip()
    side = str(intent.get("side") or "").strip().lower()
    if side not in {"buy", "sell"} or not symbol:
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="rejected",
            detail="invalid intent (missing symbol/side)",
            trade=None,
        )
        return {"ok": False, "execution": ex}

    notional = float(intent.get("notional_usdt") or 0.0)
    price = float(intent.get("price") or 0.0)
    if notional <= 0 or price <= 0 or not math.isfinite(notional) or not math.isfinite(price):
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="rejected",
            detail="invalid intent (notional/price)",
            trade=None,
        )
        return {"ok": False, "execution": ex}

    max_notional = setting.get("max_notional_usdt")
    if isinstance(max_notional, (int, float)) and math.isfinite(float(max_notional)):
        notional = min(notional, float(max_notional))

    qty = notional / price
    fee_bps = float(intent.get("fee_bps") or 10.0)
    leverage = float(intent.get("leverage") or 3.0)

    acct_id = f"user-{uid}"
    s = load_app_settings()
    use_db_paper = bool(_db_url())
    if use_db_paper:
        # DB-backed paper account snapshot (single source of truth in production)
        snap = _db_get_or_init_paper_account(uid, start_usdt=float(s.paper.start_usdt))
        acct = load_or_init_account(
            runs_dir=RUNS_DIR, account_id=acct_id, start_usdt=float(s.paper.start_usdt)
        )
        # Hydrate file-based object with DB state for deterministic execution logic reuse.
        acct.cash_usdt = float(snap.get("cash_usdt") or acct.cash_usdt)
        acct.realized_pnl_usdt = float(snap.get("realized_pnl_usdt") or acct.realized_pnl_usdt)
        # Positions are stored as arrays in snapshot; keep compatibility with PaperAccount loader
        # by writing a temp-ish json dict shape into object maps.
        acct.spot_positions = {}
        for p in snap.get("spot_positions") or []:
            if isinstance(p, dict) and p.get("symbol"):
                from paper_account import SpotPosition

                acct.spot_positions[str(p["symbol"])] = SpotPosition(
                    symbol=str(p["symbol"]),
                    qty=float(p.get("qty") or 0.0),
                    avg_entry=float(p.get("avg_entry") or 0.0),
                )
        acct.perp_positions = {}
        for p in snap.get("perp_positions") or []:
            if isinstance(p, dict) and p.get("symbol"):
                from paper_account import PerpPosition

                acct.perp_positions[str(p["symbol"])] = PerpPosition(
                    symbol=str(p["symbol"]),
                    qty_signed=float(p.get("qty_signed") or 0.0),
                    avg_entry=float(p.get("avg_entry") or 0.0),
                    leverage=float(p.get("leverage") or 1.0),
                    margin_locked_usdt=float(p.get("margin_locked_usdt") or 0.0),
                )
    else:
        acct = load_or_init_account(
            runs_dir=RUNS_DIR, account_id=acct_id, start_usdt=float(s.paper.start_usdt)
        )

    try:
        if instrument == "perp":
            trade = apply_perp_fill(
                account=acct,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                fee_bps=fee_bps,
                leverage=leverage,
            )
        else:
            trade = apply_spot_fill(
                account=acct,
                symbol=symbol,
                side=side,
                qty=qty,
                price=price,
                fee_bps=fee_bps,
            )
        save_account(runs_dir=RUNS_DIR, account=acct)
        append_trade(runs_dir=RUNS_DIR, account_id=acct_id, trade=trade)
        if use_db_paper:
            # Persist back to DB canonical snapshot.
            _db_save_paper_account(uid, acct.snapshot(instrument=instrument))
            _db_append_paper_trade(uid, trade)
        mark_inbox_read(uid, int(inbox_id))
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="executed",
            detail=f"executed {instrument} {side} {symbol} notional={notional:.2f} price={price:.8f}",
            trade=trade,
        )
        return {"ok": True, "execution": ex, "account": acct.snapshot(instrument=instrument)}
    except Exception as e:
        ex = record_execution(
            user_id=uid,
            provider=provider,
            signal_id=signal_id,
            inbox_id=int(inbox_id),
            status="failed",
            detail=str(e),
            trade=None,
        )
        return {"ok": False, "execution": ex}


@router.post("/copy/execute")
def post_execute(request: Request, req: ExecuteInboxRequest) -> dict[str, Any]:
    """Execute an ops signal into the user's local paper account.

    The signal must be published as kind=ops and include meta.intent:
      {
        "instrument": "spot"|"perp",
        "symbol": "BTC/USDT",
        "side": "buy"|"sell",
        "notional_usdt": 100.0,
        "price": 65000.0,
        "fee_bps": 10.0,
        "leverage": 3.0   # only for perp
      }
    """
    if not _db_url():
        raise HTTPException(status_code=400, detail="Copy requires DATABASE_URL (Postgres mode).")
    uid = require_user_id(request)
    return execute_inbox_item(user_id=uid, inbox_id=int(req.inbox_id))


@router.get("/copy/executions")
def get_executions(request: Request, limit: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
    if not _db_url():
        return {"count": 0, "executions": []}
    uid = require_user_id(request)
    rows = list_executions(uid, limit=int(limit))
    return {"count": len(rows), "executions": rows}
