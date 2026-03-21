"""Agent trace dataclasses for UI and telemetry (thought chain, proposal, veto)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TraceActor:
    id: str
    role: str
    persona_ref: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceContext:
    pair: Optional[str] = None
    signal: Optional[str] = None
    confidence: Optional[float] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = {"pair": self.pair, "signal": self.signal, "confidence": self.confidence}
        d = {k: v for k, v in d.items() if v is not None}
        d.update(self.extra)
        return d


@dataclass
class ThoughtStep:
    step: int
    label: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceProposal:
    action: str
    params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TraceVetoStatus:
    checked_by: str
    status: str  # APPROVED | REJECTED | MODIFIED
    reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AgentTrace:
    """
    Single agent thought-chain record for streaming to UI / OpenClaw.

    Matches the expert spec: trace_id, timestamp, actor, context,
    thought_process, proposal, veto_status.
    """

    trace_id: str
    timestamp: str
    actor: TraceActor
    context: TraceContext
    thought_process: List[ThoughtStep]
    proposal: Optional[TraceProposal] = None
    veto_status: Optional[TraceVetoStatus] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "actor": self.actor.to_dict(),
            "context": self.context.to_dict(),
            "thought_process": [t.to_dict() for t in self.thought_process],
        }
        if self.proposal is not None:
            d["proposal"] = self.proposal.to_dict()
        if self.veto_status is not None:
            d["veto_status"] = self.veto_status.to_dict()
        return d
