from __future__ import annotations

import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field

from storage.leadpage_db import create_user, get_user_by_email, get_user_by_id

router = APIRouter(tags=["auth"])

_PWD = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _jwt_secret() -> str:
    sec = (os.getenv("AIMM_AUTH_SECRET") or "").strip()
    if not sec:
        env = (os.getenv("AIMM_ENV") or os.getenv("ENV") or "").strip().lower()
        if env in {"prod", "production"}:
            raise RuntimeError("AIMM_AUTH_SECRET is required in production")
        # Dev fallback; for production set AIMM_AUTH_SECRET.
        sec = "dev-secret-change-me"
    return sec


def _jwt_alg() -> str:
    return "HS256"


def _jwt_ttl_sec() -> int:
    raw = (os.getenv("AIMM_AUTH_TTL_SEC") or "").strip() or "86400"
    try:
        v = int(raw)
    except Exception:
        v = 86400
    return max(300, min(30 * 86400, v))


def issue_token(*, user_id: int) -> str:
    now = int(time.time())
    payload = {"sub": str(int(user_id)), "iat": now, "exp": now + _jwt_ttl_sec()}
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_alg())


def _presented_bearer(request: Request) -> str | None:
    auth = (request.headers.get("authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip() or None
    return None


def require_user_id(request: Request) -> int:
    token = _presented_bearer(request)
    if not token:
        raise HTTPException(status_code=401, detail="missing bearer token")
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_alg()])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="invalid token") from e
    sub = payload.get("sub")
    try:
        uid = int(str(sub))
    except Exception as e:
        raise HTTPException(status_code=401, detail="invalid token subject") from e
    if get_user_by_id(uid) is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return uid


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=200)
    password: str = Field(..., min_length=1, max_length=200)


@router.post("/auth/register")
def register(req: RegisterRequest) -> dict[str, Any]:
    email = req.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="invalid email")
    if get_user_by_email(email) is not None:
        raise HTTPException(status_code=400, detail="email already registered")
    pw_hash = _PWD.hash(req.password)
    uid = create_user(email=email, password_hash=pw_hash)
    return {"ok": True, "user_id": uid, "token": issue_token(user_id=uid)}


@router.post("/auth/login")
def login(req: LoginRequest) -> dict[str, Any]:
    email = req.email.strip().lower()
    u = get_user_by_email(email)
    if u is None or not _PWD.verify(req.password, u.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    return {"ok": True, "user_id": int(u.id), "token": issue_token(user_id=int(u.id))}


@router.get("/auth/me")
def me(request: Request) -> dict[str, Any]:
    uid = require_user_id(request)
    u = get_user_by_id(uid)
    return {"ok": True, "user": {"id": int(uid), "email": u.email if u else None}}
