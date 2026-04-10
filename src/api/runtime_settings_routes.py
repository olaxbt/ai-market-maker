"""File-based runtime settings API (v1).

Currently supports policy overrides written to `config/runtime_settings.json`
so deterministic parts of the system can change behavior without restarts.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["runtime_settings"])


def _settings_path() -> Path:
    p = (os.getenv("AIMM_RUNTIME_SETTINGS_PATH") or "config/runtime_settings.json").strip()
    return Path(p)


def _read_settings() -> dict[str, Any]:
    p = _settings_path()
    if not p.is_file():
        return {}
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return {}
    try:
        obj = json.loads(raw)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _write_settings(obj: dict[str, Any]) -> None:
    p = _settings_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class PolicyPatch(BaseModel):
    # Keep this permissive; policy_loader ignores unknown keys.
    policy: dict[str, Any] = Field(default_factory=dict)


@router.get("/runtime-settings")
def get_runtime_settings() -> dict[str, Any]:
    return {"path": str(_settings_path()), "settings": _read_settings()}


@router.put("/runtime-settings/policy")
def put_runtime_policy(patch: PolicyPatch) -> dict[str, Any]:
    obj = _read_settings()
    obj_policy = obj.get("policy") if isinstance(obj.get("policy"), dict) else {}
    obj["policy"] = {**obj_policy, **(patch.policy or {})}
    _write_settings(obj)
    return {"ok": True, "path": str(_settings_path()), "settings": obj}


__all__ = ["router"]
