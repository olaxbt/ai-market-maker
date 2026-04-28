from __future__ import annotations

import time
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.auth_routes import require_user_id
from api.leadpage_routes import _auth_provider_db_or_env_or_401  # reuse provider auth
from storage.leadpage_db import database_url as _db_url
from storage.leadpage_db import feed_signals as _db_feed_signals
from storage.leadpage_db import insert_signal as _db_insert_signal
from storage.leadpage_db import list_following as _db_list_following

router = APIRouter(tags=["signals"])


class PublishSignalRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=80)
    kind: Literal["strategy", "ops", "discussion"] = Field("strategy")
    title: str = Field(..., min_length=2, max_length=200)
    body: str = Field(..., min_length=1, max_length=8000)
    ticker: str | None = Field(None, max_length=80)
    result_provider: str | None = Field(None, max_length=80)
    result_run_id: str | None = Field(None, max_length=160)
    meta: dict[str, Any] | None = None


@router.post("/signals/publish")
def post_publish_signal(request: Request, req: PublishSignalRequest) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(status_code=400, detail="Signals require DATABASE_URL (Postgres mode).")
    _auth_provider_db_or_env_or_401(request, req.provider)
    row = _db_insert_signal(
        provider=req.provider,
        kind=req.kind,
        title=req.title,
        body=req.body,
        ticker=req.ticker,
        result_provider=req.result_provider,
        result_run_id=req.result_run_id,
        meta=req.meta or {},
    )
    return {"ok": True, "signal": row}


@router.get("/signals/feed")
def get_signal_feed(
    limit: int = Query(100, ge=1, le=1000),
    provider: str | None = Query(None),
) -> dict[str, Any]:
    if not _db_url():
        return {"count": 0, "signals": []}
    rows = _db_feed_signals(limit=int(limit), provider=provider)
    return {"count": len(rows), "signals": rows}


@router.get("/signals/following")
def get_following_feed(
    request: Request,
    limit: int = Query(100, ge=1, le=1000),
) -> dict[str, Any]:
    """Personalized feed: signals from providers the authenticated user follows."""
    if not _db_url():
        return {"count": 0, "signals": []}
    uid = require_user_id(request)
    provs = set(_db_list_following(uid))
    pool = max(int(limit) * 6, 200)
    rows_all = _db_feed_signals(limit=pool, provider=None)
    rows = [r for r in rows_all if r.get("provider") in provs][: int(limit)]
    return {"count": len(rows), "signals": rows}


def _sse(data: dict[str, Any]) -> bytes:
    # SSE event with json payload.
    import json as _json

    payload = _json.dumps(data, separators=(",", ":"), default=str)
    return f"data: {payload}\n\n".encode("utf-8")


@router.get("/signals/stream")
def stream_signals(
    request: Request,
    provider: str | None = Query(None),
    poll_sec: float = Query(1.0, ge=0.25, le=10.0),
    limit: int = Query(50, ge=1, le=200),
) -> StreamingResponse:
    """Server-Sent Events stream of latest signals (public).

    This is a simple polling-based SSE stream over Postgres; suitable for lightweight realtime UI.
    """
    if not _db_url():
        return StreamingResponse(
            iter([_sse({"type": "error", "error": "db_not_enabled"})]),
            media_type="text/event-stream",
        )

    def gen():
        last_id = 0
        # initial snapshot
        rows = _db_feed_signals(limit=int(limit), provider=provider)
        for r in reversed(rows):
            rid = int(r.get("id") or 0)
            last_id = max(last_id, rid)
            yield _sse({"type": "signal", "signal": r})
        yield _sse({"type": "ready", "last_id": last_id})

        while True:
            # Client disconnected?
            if getattr(request, "is_disconnected", None):
                try:
                    if request.is_disconnected():
                        return
                except Exception:
                    pass

            rows2 = _db_feed_signals(limit=200, provider=provider)
            new_rows = []
            for r in rows2:
                rid = int(r.get("id") or 0)
                if rid > last_id:
                    new_rows.append(r)
            if new_rows:
                for r in reversed(new_rows):
                    last_id = max(last_id, int(r.get("id") or 0))
                    yield _sse({"type": "signal", "signal": r})
            else:
                yield _sse({"type": "ping", "ts": int(time.time())})
            time.sleep(float(poll_sec))

    return StreamingResponse(gen(), media_type="text/event-stream")
