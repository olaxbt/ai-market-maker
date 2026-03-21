"""
LogPublisher: bridge from agent state to Agent Trace JSON for the UI.

Converts agent outputs (reasoning, proposal, veto) into the agent_trace schema
and publishes to in-memory buffer, optional file, and/or callback (e.g. WebSocket later).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from schemas.agent_trace import (
    AgentTrace,
    ThoughtStep,
    TraceActor,
    TraceContext,
    TraceProposal,
    TraceVetoStatus,
)


def _make_trace_id(prefix: str = "tx") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class LogPublisher:
    """
    Publishes agent thought-chain traces in the expert spec format.

    UI (Agentic Nexus / OpenClaw) can consume the trace list or subscribe
    via callback. Optionally append to a file for replay.
    """

    def __init__(
        self,
        run_id: Optional[str] = None,
        log_path: Optional[Path] = None,
        on_trace: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.run_id = run_id or _make_trace_id("run")
        self.log_path = log_path
        self.on_trace = on_trace
        self._traces: List[AgentTrace] = []

    def publish(
        self,
        actor_id: str,
        role: str,
        thought_process: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        proposal: Optional[Dict[str, Any]] = None,
        veto_status: Optional[Dict[str, Any]] = None,
        persona_ref: Optional[str] = None,
    ) -> AgentTrace:
        """
        Build and publish one agent trace.

        thought_process: list of {"step", "label", "detail"} or ThoughtStep-like dicts.
        context: optional {"pair", "signal", "confidence", ...}.
        proposal: optional {"action", "params"}.
        veto_status: optional {"checked_by", "status", "reason"}.
        """
        trace_id = _make_trace_id()
        timestamp = _ts()

        actor = TraceActor(id=actor_id, role=role, persona_ref=persona_ref)
        ctx = TraceContext(
            pair=context.get("pair") if context else None,
            signal=context.get("signal") if context else None,
            confidence=context.get("confidence") if context else None,
            extra={k: v for k, v in (context or {}).items() if k not in ("pair", "signal", "confidence")},
        )
        steps = [
            ThoughtStep(
                step=s.get("step", i + 1),
                label=s.get("label", ""),
                detail=s.get("detail", ""),
            )
            for i, s in enumerate(thought_process)
        ]
        prop = None
        if proposal:
            prop = TraceProposal(action=proposal.get("action", ""), params=proposal.get("params", {}))
        veto = None
        if veto_status:
            veto = TraceVetoStatus(
                checked_by=veto_status.get("checked_by", ""),
                status=veto_status.get("status", "APPROVED"),
                reason=veto_status.get("reason"),
            )

        trace = AgentTrace(
            trace_id=trace_id,
            timestamp=timestamp,
            actor=actor,
            context=ctx,
            thought_process=steps,
            proposal=prop,
            veto_status=veto,
        )
        self._traces.append(trace)
        payload = trace.to_dict()
        payload["run_id"] = self.run_id

        if self.log_path:
            try:
                with open(self.log_path, "a") as f:
                    f.write(json.dumps(payload, default=str) + "\n")
            except OSError:
                pass
        if self.on_trace:
            try:
                self.on_trace(payload)
            except Exception:
                pass
        return trace

    def publish_from_agent(
        self,
        name: str,
        role: str,
        memory: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None,
        proposal: Optional[Dict[str, Any]] = None,
        veto_status: Optional[Dict[str, Any]] = None,
        persona_ref: Optional[str] = None,
    ) -> AgentTrace:
        """
        Build thought_process from BaseAgent-style memory (agent, role, thought, decision).
        """
        thought_process = [
            {"step": i + 1, "label": m.get("thought", "")[:50] or "Step", "detail": m.get("thought", "")}
            for i, m in enumerate(memory)
        ]
        if not thought_process:
            thought_process = [{"step": 1, "label": "Reasoning", "detail": "No steps recorded."}]
        return self.publish(
            actor_id=name.lower().replace(" ", "-"),
            role=role,
            thought_process=thought_process,
            context=context,
            proposal=proposal,
            veto_status=veto_status,
            persona_ref=persona_ref,
        )

    def traces(self) -> List[AgentTrace]:
        return list(self._traces)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "traces": [t.to_dict() for t in self._traces],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str, indent=2)

    def clear(self) -> None:
        self._traces.clear()


_current_publisher: Optional[LogPublisher] = None


def get_log_publisher() -> Optional[LogPublisher]:
    return _current_publisher


def set_log_publisher(publisher: Optional[LogPublisher]) -> None:
    global _current_publisher
    _current_publisher = publisher
