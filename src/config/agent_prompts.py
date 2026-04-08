"""File-based prompt/settings store for agent nodes.

This is the first step towards making the UI prompt editor *real*:
- The backend loads this file to decide model + prompt text for LLM-backed nodes.
- The UI updates it through an API endpoint.
- The Flow payload exports the current settings under `agent_prompts`.

Storage is JSON to avoid additional dependencies (YAML).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


def _default_prompts_path() -> Path:
    p = (os.getenv("AIMM_AGENT_PROMPTS_PATH") or "config/agent_prompts.json").strip()
    return Path(p)


@dataclass(frozen=True)
class AgentPromptSettings:
    node_id: str
    actor_id: str
    system_prompt: str
    task_prompt: str
    cot_enabled: bool
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[str] | None = None

    def to_public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # The Nexus payload JSON schema expects these fields to be either omitted or typed,
        # not `null`. Strip `None` values.
        for k in ("model", "temperature", "max_tokens", "tools"):
            if d.get(k) is None:
                d.pop(k, None)
        return d


def _coerce_row(row: Any) -> AgentPromptSettings | None:
    if not isinstance(row, dict):
        return None
    node_id = str(row.get("node_id") or "").strip()
    actor_id = str(row.get("actor_id") or "").strip()
    system_prompt = str(row.get("system_prompt") or "")
    task_prompt = str(row.get("task_prompt") or "")
    cot_enabled = bool(row.get("cot_enabled"))
    if not node_id or not actor_id:
        return None
    model = row.get("model")
    model_s = str(model).strip() if isinstance(model, str) and model.strip() else None
    temp = row.get("temperature")
    try:
        temp_f = float(temp) if temp is not None else None
    except (TypeError, ValueError):
        temp_f = None
    mt = row.get("max_tokens")
    try:
        mt_i = int(mt) if mt is not None else None
    except (TypeError, ValueError):
        mt_i = None
    tools = row.get("tools")
    tools_out = [str(x) for x in tools] if isinstance(tools, list) else None
    return AgentPromptSettings(
        node_id=node_id,
        actor_id=actor_id,
        system_prompt=system_prompt,
        task_prompt=task_prompt,
        cot_enabled=cot_enabled,
        model=model_s,
        temperature=temp_f,
        max_tokens=mt_i,
        tools=tools_out,
    )


def load_agent_prompt_settings(path: Path | None = None) -> list[AgentPromptSettings]:
    p = path or _default_prompts_path()
    if not p.is_file():
        return []
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    out: list[AgentPromptSettings] = []
    for row in data:
        ps = _coerce_row(row)
        if ps is not None:
            out.append(ps)
    return out


def save_agent_prompt_settings(rows: list[AgentPromptSettings], path: Path | None = None) -> None:
    p = path or _default_prompts_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = [r.to_public_dict() for r in rows]
    p.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def upsert_agent_prompt_setting(
    row: AgentPromptSettings, *, path: Path | None = None
) -> list[AgentPromptSettings]:
    """Update by node_id, or append if missing. Returns the new full list."""
    rows = load_agent_prompt_settings(path)
    out: list[AgentPromptSettings] = []
    replaced = False
    for r in rows:
        if r.node_id == row.node_id:
            out.append(row)
            replaced = True
        else:
            out.append(r)
    if not replaced:
        out.append(row)
    save_agent_prompt_settings(out, path)
    return out


def prompt_settings_by_actor(*, path: Path | None = None) -> dict[str, AgentPromptSettings]:
    """Convenience lookup: actor_id -> settings (first wins)."""
    out: dict[str, AgentPromptSettings] = {}
    for r in load_agent_prompt_settings(path):
        out.setdefault(r.actor_id, r)
    return out


__all__ = [
    "AgentPromptSettings",
    "load_agent_prompt_settings",
    "prompt_settings_by_actor",
    "save_agent_prompt_settings",
    "upsert_agent_prompt_setting",
]
