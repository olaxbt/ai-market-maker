from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from api.auth_routes import require_user_id
from storage.leadpage_db import (
    database_url as _db_url,
)
from storage.leadpage_db import (
    follow_provider,
    inbox_items,
    list_following,
    mark_inbox_read,
    unfollow_provider,
)

router = APIRouter(tags=["social"])


class FollowRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=80)


@router.get("/social/following")
def get_following(request: Request) -> dict[str, Any]:
    if not _db_url():
        return {"providers": []}
    uid = require_user_id(request)
    return {"providers": list_following(uid)}


@router.post("/social/follow")
def post_follow(request: Request, req: FollowRequest) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(status_code=400, detail="Follow requires DATABASE_URL (Postgres mode).")
    uid = require_user_id(request)
    follow_provider(user_id=uid, provider=req.provider)
    return {"ok": True}


@router.post("/social/unfollow")
def post_unfollow(request: Request, req: FollowRequest) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(
            status_code=400, detail="Unfollow requires DATABASE_URL (Postgres mode)."
        )
    uid = require_user_id(request)
    unfollow_provider(user_id=uid, provider=req.provider)
    return {"ok": True}


@router.get("/social/inbox")
def get_inbox(
    request: Request,
    limit: int = Query(200, ge=1, le=2000),
) -> dict[str, Any]:
    if not _db_url():
        return {"count": 0, "items": []}
    uid = require_user_id(request)
    rows = inbox_items(uid, limit=int(limit))
    return {"count": len(rows), "items": rows}


class MarkReadRequest(BaseModel):
    inbox_id: int = Field(..., ge=1)


@router.post("/social/inbox/mark-read")
def post_mark_read(request: Request, req: MarkReadRequest) -> dict[str, Any]:
    if not _db_url():
        raise HTTPException(status_code=400, detail="Inbox requires DATABASE_URL (Postgres mode).")
    uid = require_user_id(request)
    mark_inbox_read(uid, int(req.inbox_id))
    return {"ok": True}
