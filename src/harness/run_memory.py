from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from api.runtime_settings_routes import _read_settings as _read_runtime_settings
from config.app_settings import AppSettings


@dataclass(frozen=True)
class RunMemoryConfig:
    recent_views_max: int = 60
    recent_decisions_max: int = 60
    recent_tool_events_max: int = 60


def run_memory_config(settings: AppSettings) -> RunMemoryConfig:
    # Allow runtime override via config/runtime_settings.json for operator UX.
    rt = _read_runtime_settings()
    hm_rt = rt.get("harness_memory") if isinstance(rt.get("harness_memory"), dict) else {}
    hm = settings.harness_memory
    return RunMemoryConfig(
        recent_views_max=int(hm_rt.get("recent_views_max", hm.recent_views_max)),
        recent_decisions_max=int(hm_rt.get("recent_decisions_max", hm.recent_decisions_max)),
        recent_tool_events_max=int(hm_rt.get("recent_tool_events_max", hm.recent_tool_events_max)),
    )


class RunWorkingMemory:
    """Run-scoped working memory (bounded, serializable).

    Design references:
    - Hermes/Mnemosyne "working memory" tier: bounded hot context.
    - OpenClaw transparency principle: memory is auditable; avoid hidden state.

    This is *not* a user preference store; it is run-ops memory: what the system saw and decided.
    """

    def __init__(self, *, cfg: RunMemoryConfig):
        self._views: deque[dict[str, Any]] = deque(maxlen=max(0, int(cfg.recent_views_max)))
        self._decisions: deque[dict[str, Any]] = deque(maxlen=max(0, int(cfg.recent_decisions_max)))
        self._tool_events: deque[dict[str, Any]] = deque(
            maxlen=max(0, int(cfg.recent_tool_events_max))
        )

    def record_view(self, view: dict[str, Any]) -> None:
        if self._views.maxlen == 0:
            return
        if isinstance(view, dict):
            self._views.append(dict(view))

    def record_decision(self, decision: dict[str, Any]) -> None:
        if self._decisions.maxlen == 0:
            return
        if isinstance(decision, dict):
            self._decisions.append(dict(decision))

    def record_tool_event_summary(self, event: dict[str, Any]) -> None:
        if self._tool_events.maxlen == 0:
            return
        if isinstance(event, dict):
            self._tool_events.append(dict(event))

    def to_shared_memory_fragment(self) -> dict[str, Any]:
        return {
            "recent_views": list(self._views),
            "recent_decisions": list(self._decisions),
            "recent_tool_events": list(self._tool_events),
        }


class IterationReceiptWriter:
    """Append-only JSONL receipts (auditable, UI-friendly)."""

    def __init__(self, *, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            self.path.unlink()

    def append(self, rec: dict[str, Any]) -> None:
        if not isinstance(rec, dict):
            return
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, default=str) + "\n")
        except Exception:
            return


def now_s() -> int:
    return int(time.time())


__all__ = [
    "RunMemoryConfig",
    "run_memory_config",
    "RunWorkingMemory",
    "IterationReceiptWriter",
    "now_s",
]
