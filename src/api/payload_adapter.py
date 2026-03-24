"""Adapt FlowEvent JSONL logs to the web `NexusPayload` shape."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

NODE_REGISTRY: List[Dict[str, str]] = [
    {"id": "n1", "actor": "market_scan", "label": "Market Scan", "role": "Market Scan"},
    {"id": "n2", "actor": "price_pattern", "label": "Price Pattern", "role": "Price Pattern"},
    {"id": "n3", "actor": "sentiment", "label": "Sentiment", "role": "Sentiment"},
    {"id": "n4", "actor": "stat_arb", "label": "Stat Arb", "role": "Stat Arb"},
    {"id": "n5", "actor": "quant", "label": "Quant", "role": "Quant"},
    {"id": "n6", "actor": "valuation", "label": "Valuation", "role": "Valuation"},
    {"id": "n7", "actor": "liquidity", "label": "Liquidity", "role": "Liquidity"},
    {"id": "n8", "actor": "risk", "label": "Risk", "role": "Risk"},
    {"id": "n9", "actor": "bull_case", "label": "Bull Case", "role": "Bull Case"},
    {"id": "n10", "actor": "bear_case", "label": "Bear Case", "role": "Bear Case"},
    {
        "id": "n11",
        "actor": "signal_arbitrator",
        "label": "Signal Arbitrator",
        "role": "Signal Arbitrator",
    },
    {
        "id": "n12",
        "actor": "portfolio_proposal",
        "label": "Portfolio Proposal",
        "role": "Portfolio Proposal",
    },
    {"id": "n13", "actor": "risk_guard", "label": "Risk Guard", "role": "Risk Guard"},
    {"id": "n14", "actor": "portfolio_execute", "label": "Execution", "role": "Execution"},
]

EDGES: List[Dict[str, str]] = [
    {"from": "n1", "to": "n2"},
    {"from": "n1", "to": "n3"},
    {"from": "n1", "to": "n4"},
    {"from": "n1", "to": "n5"},
    {"from": "n1", "to": "n6"},
    {"from": "n1", "to": "n7"},
    {"from": "n2", "to": "n8"},
    {"from": "n3", "to": "n8"},
    {"from": "n4", "to": "n8"},
    {"from": "n5", "to": "n8"},
    {"from": "n6", "to": "n8"},
    {"from": "n7", "to": "n8"},
    {"from": "n8", "to": "n9"},
    {"from": "n8", "to": "n10"},
    {"from": "n9", "to": "n11"},
    {"from": "n10", "to": "n11"},
    {"from": "n11", "to": "n12"},
    {"from": "n12", "to": "n13"},
    {"from": "n13", "to": "n14"},
]


def _node(actor: str) -> Dict[str, str]:
    for n in NODE_REGISTRY:
        if n["actor"] == actor:
            return n
    return NODE_REGISTRY[0]


def _topology() -> Dict[str, Any]:
    nodes = [
        {
            "id": n["id"],
            "actor": n["actor"],
            "label": n["label"],
            "status": "PENDING",
            "summary": "",
        }
        for n in NODE_REGISTRY
    ]
    return {"nodes": nodes, "edges": EDGES}


def _read_events(log_path: Path) -> List[Dict[str, Any]]:
    if not log_path.exists():
        return []
    rows: List[Tuple[int, Dict[str, Any]]] = []
    with log_path.open() as f:
        for idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            rows.append((idx, json.loads(line)))

    def sort_key(item: Tuple[int, Dict[str, Any]]) -> Tuple[str, int]:
        idx, event = item
        raw_ts = str(event.get("ts") or "")
        try:
            parsed = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
            return (parsed.isoformat(), idx)
        except ValueError:
            return (raw_ts, idx)

    rows.sort(key=sort_key)
    return [event for _, event in rows]


def _message_kind(kind: str) -> str:
    if kind == "node_start":
        return "status"
    if kind == "node_end":
        return "handoff"
    if kind in {"reasoning", "risk_guard"}:
        return "thought"
    return "status"


def build_nexus_payload(log_path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return `(payload, events)` where payload matches `web/src/types/nexus-payload.ts`."""
    events = _read_events(log_path)
    run_id = log_path.stem.replace(".events", "")
    topology = _topology()
    traces: List[Dict[str, Any]] = []
    message_log: List[Dict[str, Any]] = []
    seq = 1
    trace_seq = 1
    ticker = "BTC/USDT"
    flow_status = "RUNNING"
    node_status: Dict[str, str] = {n["actor"]: "PENDING" for n in NODE_REGISTRY}
    node_summary: Dict[str, str] = {}
    latest_trace_for_actor: Dict[str, str] = {}

    for ev in events:
        kind = str(ev.get("kind") or "")
        ts = str(ev.get("ts") or "")
        p = ev.get("payload", {}) or {}
        actor = str(p.get("node") or p.get("agent") or "market_scan")
        node = _node(actor)
        node_id = node["id"]

        if kind == "node_start":
            node_status[actor] = "ACTIVE"
            ticker = str(p.get("ticker") or ticker)
            node_summary[actor] = "Running"
        elif kind == "node_end":
            if p.get("error"):
                node_status[actor] = "PENDING"
                node_summary[actor] = f"Error: {p.get('error')}"
            else:
                node_status[actor] = "COMPLETED"
                node_summary[actor] = str(p.get("summary") or "Completed")
        elif kind == "execution":
            flow_status = "COMPLETED" if p.get("status") == "executed" else "VETOED"
        elif kind == "risk_guard":
            status = str(p.get("status") or "UNKNOWN").upper()
            if status == "VETOED":
                flow_status = "VETOED"

        thought_process: List[Dict[str, Any]] = []
        content: Dict[str, Any] = {"context": {"pair": ticker}}
        log_message = ""

        if kind == "reasoning":
            thought = str(p.get("thought") or "")
            decision = p.get("decision")
            thought_process.append({"step": 1, "label": "REASONING", "detail": thought})
            if isinstance(decision, dict) and "action" in decision and "params" in decision:
                content["proposal"] = {
                    "action": decision.get("action"),
                    "params": decision.get("params"),
                }
            signal = (p.get("extra") or {}).get("signal")
            confidence = (p.get("extra") or {}).get("confidence")
            if signal is not None:
                content["context"]["signal"] = signal
            if confidence is not None:
                content["context"]["confidence"] = confidence
            log_message = thought or "Reasoning updated"
        elif kind == "risk_guard":
            status = str(p.get("status") or "UNKNOWN")
            risk_reasoning = p.get("reasoning") or {}
            reason = str(risk_reasoning.get("thought") or status)
            thought_process.append({"step": 1, "label": "RISK_GUARD", "detail": reason})
            content["veto_status"] = {
                "checked_by": "risk_guard",
                "status": status,
                "reason": reason,
            }
            log_message = f"Risk guard: {status}"
        elif kind == "execution":
            message = str(p.get("message") or p.get("status") or "execution")
            thought_process.append({"step": 1, "label": "EXECUTION", "detail": message})
            log_message = message
        elif kind == "node_end":
            summary = str(p.get("summary") or "completed")
            log_message = f"{actor}: {summary}"
        elif kind == "node_start":
            log_message = f"{actor}: started"

        if kind == "node_start":
            thought_process.append({"step": 1, "label": "STATUS", "detail": log_message})
        elif kind == "node_end":
            thought_process.append({"step": 1, "label": "HANDOFF", "detail": log_message})

        trace_id = None
        if thought_process:
            trace_id = f"trace-{trace_seq:05d}"
            parent_id = latest_trace_for_actor.get(actor)
            traces.append(
                {
                    "trace_id": trace_id,
                    "node_id": node_id,
                    "parent_id": parent_id,
                    "timestamp": ts,
                    "actor": {
                        "id": actor,
                        "role": node["role"],
                    },
                    "content": {
                        "thought_process": thought_process,
                        **content,
                    },
                }
            )
            latest_trace_for_actor[actor] = trace_id
            trace_seq += 1

        if log_message:
            message_log.append(
                {
                    "seq": seq,
                    "ts": ts,
                    "node_id": node_id,
                    "actor_id": actor,
                    "kind": _message_kind(kind),
                    "message": log_message,
                    "trace_id": trace_id,
                }
            )
            seq += 1

    for n in topology["nodes"]:
        actor = n["actor"]
        n["status"] = node_status.get(actor, "PENDING")
        if actor in node_summary:
            n["summary"] = node_summary[actor]
        elif n["status"] == "COMPLETED":
            n["summary"] = "Completed"
        elif n["status"] == "ACTIVE":
            n["summary"] = "Running"
        else:
            n["summary"] = ""

    if not events:
        flow_status = "IDLE"
    elif flow_status == "RUNNING":
        # No explicit execution event (e.g. veto route or partial run); infer completion.
        if all(node_status.get(n["actor"]) == "COMPLETED" for n in NODE_REGISTRY):
            flow_status = "COMPLETED"

    payload = {
        "metadata": {
            "run_id": run_id,
            "ticker": ticker,
            "status": flow_status,
            "version": "0.4.0-aligned",
            "source": "flow_events_jsonl",
            "kpis": {"latency": "streaming"},
        },
        "topology": topology,
        "traces": traces,
        "message_log": message_log,
    }
    return payload, events
