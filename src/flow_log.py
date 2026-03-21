"""
Flow event repo: in-memory (and optional file) log for pipeline events.

The UI (nexus dashboard) can read from this to display flow progress,
reasoning, risk veto, and execution. Wire the workflow to push events
via FlowEventRepo.emit().
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.flow_events import FlowEvent


class FlowEventRepo:
    """
    Collects flow events for a run. UI can consume via .events() or .to_json().
    """

    def __init__(self, run_id: Optional[str] = None, log_path: Optional[Path] = None):
        self.run_id = run_id
        self.log_path = log_path
        self._events: List[FlowEvent] = []

    def emit(self, event: FlowEvent) -> None:
        if self.run_id and event.run_id is None:
            event = FlowEvent(
                kind=event.kind,
                ts=event.ts,
                run_id=self.run_id,
                payload=event.payload,
            )
        self._events.append(event)
        if self.log_path:
            self._append_to_file(event)

    def _append_to_file(self, event: FlowEvent) -> None:
        try:
            with open(self.log_path, "a") as f:
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except OSError:
            pass

    def events(self) -> List[FlowEvent]:
        return list(self._events)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self._events],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)

    def clear(self) -> None:
        self._events.clear()


# Global repo for the current run; workflow can set this before invoke.
_current_repo: Optional[FlowEventRepo] = None


def get_flow_repo() -> Optional[FlowEventRepo]:
    return _current_repo


def set_flow_repo(repo: Optional[FlowEventRepo]) -> None:
    global _current_repo
    _current_repo = repo
