from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.auth_routes import require_user_id
from storage.leadpage_db import (
    create_provider_for_user,
    list_providers_for_user,
    rotate_provider_secret,
)

router = APIRouter(tags=["provider-admin"])


class CreateProviderRequest(BaseModel):
    provider: str = Field(..., min_length=2, max_length=80)


@router.get("/admin/providers")
def get_my_providers(request: Request) -> dict[str, Any]:
    uid = require_user_id(request)
    return {"providers": list_providers_for_user(uid)}


@router.post("/admin/providers")
def post_create_provider(request: Request, req: CreateProviderRequest) -> dict[str, Any]:
    uid = require_user_id(request)
    provider = req.provider.strip()
    if not provider.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="provider must be alnum plus -/_")
    try:
        create_provider_for_user(provider=provider, user_id=uid)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    # Rotate once on create so user gets a usable secret.
    secret = rotate_provider_secret(provider=provider, user_id=uid)
    return {"ok": True, "provider": provider, "secret": secret}


@router.post("/admin/providers/{provider}/rotate-secret")
def post_rotate_secret(request: Request, provider: str) -> dict[str, Any]:
    uid = require_user_id(request)
    try:
        secret = rotate_provider_secret(provider=provider, user_id=uid)
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"ok": True, "provider": provider, "secret": secret}
