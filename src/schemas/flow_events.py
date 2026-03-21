"""
Structured log and message schema for the agentic flow.

Used by the pipeline to emit events and by the UI (nexus dashboard) to display
flow progress, reasoning, risk veto, and execution results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class FlowEventKind(str, Enum):
    NODE_START = "node_start"
    NODE_END = "node_end"
    REASONING = "reasoning"
    RISK_GUARD = "risk_guard"
    EXECUTION = "execution"


@dataclass
class NodeStartPayload:
    node: str
    ticker: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NodeEndPayload:
    node: str
    summary: Optional[str] = None
    output_keys: Optional[List[str]] = None
    error: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReasoningEntry:
    agent: str
    role: str
    thought: str
    decision: Any
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RiskGuardPayload:
    status: str  # APPROVED | VETOED
    risk_score: float
    reasoning: Dict[str, Any]
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPayload:
    status: str  # executed | skipped
    message: Optional[str] = None
    orders: Optional[List[Dict[str, Any]]] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FlowEvent:
    """Single event in the flow log. UI can consume this for live/playback views."""

    kind: FlowEventKind
    ts: str  # ISO timestamp
    run_id: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "ts": self.ts,
            "run_id": self.run_id,
            "payload": self.payload,
        }

    @classmethod
    def node_start(
        cls,
        node: str,
        run_id: Optional[str] = None,
        ticker: Optional[str] = None,
        **extra: Any,
    ) -> "FlowEvent":
        ts = datetime.now(timezone.utc).isoformat()
        p = NodeStartPayload(node=node, ticker=ticker, extra=dict(extra))
        return cls(kind=FlowEventKind.NODE_START, ts=ts, run_id=run_id, payload=p.to_dict())

    @classmethod
    def node_end(
        cls,
        node: str,
        run_id: Optional[str] = None,
        summary: Optional[str] = None,
        output_keys: Optional[List[str]] = None,
        error: Optional[str] = None,
        **extra: Any,
    ) -> "FlowEvent":
        ts = datetime.now(timezone.utc).isoformat()
        p = NodeEndPayload(
            node=node,
            summary=summary,
            output_keys=output_keys,
            error=error,
            extra=dict(extra),
        )
        return cls(kind=FlowEventKind.NODE_END, ts=ts, run_id=run_id, payload=p.to_dict())

    @classmethod
    def reasoning(
        cls,
        agent: str,
        role: str,
        thought: str,
        decision: Any,
        run_id: Optional[str] = None,
        **extra: Any,
    ) -> "FlowEvent":
        ts = datetime.now(timezone.utc).isoformat()
        entry = ReasoningEntry(agent=agent, role=role, thought=thought, decision=decision, extra=dict(extra))
        return cls(kind=FlowEventKind.REASONING, ts=ts, run_id=run_id, payload=entry.to_dict())

    @classmethod
    def risk_guard(
        cls,
        status: str,
        risk_score: float,
        reasoning: Dict[str, Any],
        run_id: Optional[str] = None,
        **extra: Any,
    ) -> "FlowEvent":
        ts = datetime.now(timezone.utc).isoformat()
        p = RiskGuardPayload(status=status, risk_score=risk_score, reasoning=reasoning, extra=dict(extra))
        return cls(kind=FlowEventKind.RISK_GUARD, ts=ts, run_id=run_id, payload=p.to_dict())

    @classmethod
    def execution(
        cls,
        status: str,
        run_id: Optional[str] = None,
        message: Optional[str] = None,
        orders: Optional[List[Dict[str, Any]]] = None,
        **extra: Any,
    ) -> "FlowEvent":
        ts = datetime.now(timezone.utc).isoformat()
        p = ExecutionPayload(status=status, message=message, orders=orders, extra=dict(extra))
        return cls(kind=FlowEventKind.EXECUTION, ts=ts, run_id=run_id, payload=p.to_dict())
