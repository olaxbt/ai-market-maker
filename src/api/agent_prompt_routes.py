"""Agent prompt/settings CRUD (file-based).

This is intentionally minimal for v1:
- file-backed JSON list at `AIMM_AGENT_PROMPTS_PATH` (default: config/agent_prompts.json)
- hot-reload on each request (operators can edit file or use the UI)
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from config.agent_prompts import (
    AgentPromptSettings,
    load_agent_prompt_settings,
    upsert_agent_prompt_setting,
)

from .payload_adapter import NODE_REGISTRY

router = APIRouter(tags=["agent_prompts"])


class AgentPromptPatch(BaseModel):
    system_prompt: str = Field(..., min_length=0, max_length=50_000)
    task_prompt: str = Field(..., min_length=0, max_length=50_000)
    model: str | None = Field(default=None, max_length=200)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=16, le=64_000)
    tools: list[str] | None = Field(default=None)
    cot_enabled: bool | None = Field(default=None)


def _by_node_id(rows: list[AgentPromptSettings], node_id: str) -> AgentPromptSettings | None:
    for r in rows:
        if r.node_id == node_id:
            return r
    return None


def _actor_for_node_id(node_id: str) -> str | None:
    for n in NODE_REGISTRY:
        if str(n.get("id") or "") == str(node_id):
            actor = str(n.get("actor") or "").strip()
            return actor or None
    return None


@router.get("/agent-prompts")
def list_agent_prompts() -> dict[str, Any]:
    rows = load_agent_prompt_settings()
    return {"count": len(rows), "rows": [r.to_public_dict() for r in rows]}


@router.get("/agent-prompts/{node_id}")
def get_agent_prompt(node_id: str) -> dict[str, Any]:
    rows = load_agent_prompt_settings()
    row = _by_node_id(rows, node_id=str(node_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown node_id")
    return row.to_public_dict()


@router.put("/agent-prompts/{node_id}")
def put_agent_prompt(node_id: str, patch: AgentPromptPatch) -> dict[str, Any]:
    rows = load_agent_prompt_settings()
    existing = _by_node_id(rows, node_id=str(node_id))
    actor_id = existing.actor_id if existing is not None else _actor_for_node_id(str(node_id))
    if actor_id is None:
        raise HTTPException(status_code=404, detail="Unknown node_id")
    updated = AgentPromptSettings(
        node_id=str(node_id),
        actor_id=str(actor_id),
        system_prompt=patch.system_prompt,
        task_prompt=patch.task_prompt,
        cot_enabled=(existing.cot_enabled if existing is not None else False)
        if patch.cot_enabled is None
        else bool(patch.cot_enabled),
        model=(
            patch.model.strip() if isinstance(patch.model, str) and patch.model.strip() else None
        ),
        temperature=patch.temperature,
        max_tokens=patch.max_tokens,
        tools=patch.tools,
    )
    upsert_agent_prompt_setting(updated)
    return updated.to_public_dict()


__all__ = ["router"]
