"""Adapt FlowEvent JSONL logs to the web `NexusPayload` shape."""

from __future__ import annotations

import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.agent_prompts import AgentPromptSettings, load_agent_prompt_settings
from config.app_settings import load_app_settings

# IMPORTANT: this registry must match the *actual* node names emitted by FlowEvents
# in `main._instrument_node(...)` (the `node_name` argument).
NODE_REGISTRY: List[Dict[str, str]] = [
    {"id": "n0", "actor": "policy_orchestrator", "label": "Policy Orchestrator", "role": "Policy"},
    {"id": "n1", "actor": "market_scan", "label": "Market Scan", "role": "Market Scan"},
    # Tier-0 perception layer (AIMM8)
    {
        "id": "n2",
        "actor": "monetary_sentinel",
        "label": "Monetary Sentinel",
        "role": "Macro / Liquidity",
    },
    {
        "id": "n3",
        "actor": "news_narrative_miner",
        "label": "News Narrative",
        "role": "News / Catalyst",
    },
    {"id": "n4", "actor": "pattern_recognition_bot", "label": "Pattern Bot", "role": "Patterns"},
    {
        "id": "n5",
        "actor": "statistical_alpha_engine",
        "label": "Statistical Alpha",
        "role": "Stat Alpha",
    },
    {
        "id": "n6",
        "actor": "technical_ta_engine",
        "label": "Technical TA",
        "role": "Technical Analysis",
    },
    {
        "id": "n7",
        "actor": "retail_hype_tracker",
        "label": "Retail Hype",
        "role": "Retail / Sentiment",
    },
    {"id": "n8", "actor": "pro_bias_analyst", "label": "Pro Bias", "role": "Institutional / Bias"},
    {
        "id": "n9",
        "actor": "whale_behavior_analyst",
        "label": "Whale Behavior",
        "role": "Whales / On-chain",
    },
    {
        "id": "n10",
        "actor": "liquidity_order_flow",
        "label": "Liquidity & Flow",
        "role": "Order Flow",
    },
    # Governance / synthesis
    {"id": "n11", "actor": "risk", "label": "Risk Desk", "role": "Risk"},
    {"id": "n12", "actor": "desk_debate", "label": "Desk Debate", "role": "Macro vs Tape"},
    {"id": "n13", "actor": "signal_arbitrator", "label": "Signal Arbitrator", "role": "Arbitrator"},
    {"id": "n14", "actor": "portfolio_proposal", "label": "Portfolio Proposal", "role": "PM Desk"},
    {"id": "n15", "actor": "risk_guard", "label": "Risk Guard", "role": "Veto Layer"},
    {"id": "n16", "actor": "portfolio_execute", "label": "Execution", "role": "Execution"},
    {"id": "n17", "actor": "audit", "label": "Audit", "role": "Audit"},
]

EDGES: List[Dict[str, str]] = [
    {"from": "n0", "to": "n1"},
    # Market scan fans out to Tier-0 perception.
    {"from": "n1", "to": "n2"},
    {"from": "n1", "to": "n3"},
    {"from": "n1", "to": "n4"},
    {"from": "n1", "to": "n5"},
    {"from": "n1", "to": "n6"},
    {"from": "n1", "to": "n7"},
    {"from": "n1", "to": "n8"},
    {"from": "n1", "to": "n9"},
    {"from": "n1", "to": "n10"},
    # Tier-0 converges into risk desk, then synthesis/governance.
    {"from": "n2", "to": "n11"},
    {"from": "n3", "to": "n11"},
    {"from": "n4", "to": "n11"},
    {"from": "n5", "to": "n11"},
    {"from": "n6", "to": "n11"},
    {"from": "n7", "to": "n11"},
    {"from": "n8", "to": "n11"},
    {"from": "n9", "to": "n11"},
    {"from": "n10", "to": "n11"},
    {"from": "n11", "to": "n12"},
    {"from": "n12", "to": "n13"},
    {"from": "n13", "to": "n14"},
    {"from": "n14", "to": "n15"},
    {"from": "n15", "to": "n16"},
    {"from": "n16", "to": "n17"},
]


def _node(actor: str) -> Dict[str, str]:
    for n in NODE_REGISTRY:
        if n["actor"] == actor:
            return n
    # Fallback for new/unknown nodes: render as a generic node so the UI doesn't lie.
    return {"id": actor, "actor": actor, "label": actor.replace("_", " ").title(), "role": actor}


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


def _read_events(log_path: Path, *, tail: int | None = None) -> List[Dict[str, Any]]:
    if not log_path.exists():
        return []
    if tail is not None and tail > 0:
        buf: deque[Tuple[int, Dict[str, Any]]] = deque(maxlen=int(tail))
        with log_path.open() as f:
            for idx, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                buf.append((idx, json.loads(line)))
        rows: List[Tuple[int, Dict[str, Any]]] = list(buf)
    else:
        rows = []
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


def _bar_meta_from_payload(p: Any) -> Tuple[Optional[int], str]:
    """Synthetic bar index (0-based) and bar open time label from backtest FlowEvent payload."""
    if not isinstance(p, dict):
        return (None, "")
    ex = p.get("extra")
    for d in (p, ex if isinstance(ex, dict) else None):
        if not isinstance(d, dict):
            continue
        raw = d.get("bar_step")
        if raw is None:
            continue
        try:
            step = int(raw)
        except (TypeError, ValueError):
            continue
        bt = str(d.get("bar_time_utc") or "").strip()
        return (step, bt)
    return (None, "")


def build_nexus_payload(
    log_path: Path,
    *,
    tail_events: int | None = None,
    tail_traces: int | None = None,
    tail_message_log: int | None = None,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Return `(payload, events)` where payload matches `web/src/types/nexus-payload.ts`."""
    events = _read_events(log_path, tail=tail_events)
    run_id = log_path.stem.replace(".events", "")
    topology = _topology()
    traces: List[Dict[str, Any]] = []
    message_log: List[Dict[str, Any]] = []
    seq = 1
    trace_seq = 1
    try:
        app = load_app_settings()
        ticker = str(app.market.default_ticker)
        app_universe_symbols = list(app.market.universe_symbols or [])
        app_universe_size = int(app.market.universe_size)
    except Exception:
        ticker = "BTC/USDT"
        app_universe_symbols = []
        app_universe_size = 0
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
            else:
                # Preserve non-proposal decisions (e.g. tool results) for UI rendering.
                content["decision"] = decision
            extra_obj = p.get("extra")
            if isinstance(extra_obj, dict) and extra_obj:
                content["extra"] = extra_obj
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

        bar_step, bar_time_utc = _bar_meta_from_payload(p)

        trace_id = None
        if thought_process:
            trace_id = f"trace-{trace_seq:05d}"
            parent_id = latest_trace_for_actor.get(actor)
            td: Dict[str, Any] = {
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
            if bar_step is not None:
                td["bar_step"] = bar_step
            if bar_time_utc:
                td["bar_time_utc"] = bar_time_utc
            traces.append(td)
            latest_trace_for_actor[actor] = trace_id
            trace_seq += 1

        if log_message:
            row: Dict[str, Any] = {
                "seq": seq,
                "ts": ts,
                "node_id": node_id,
                "actor_id": actor,
                "kind": _message_kind(kind),
                "message": log_message,
                "trace_id": trace_id,
            }
            if bar_step is not None:
                row["bar_step"] = bar_step
            if bar_time_utc:
                row["bar_time_utc"] = bar_time_utc
            message_log.append(row)
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
            "universe_symbols": app_universe_symbols,
            "universe_size": app_universe_size
            or (len(app_universe_symbols) if app_universe_symbols else 0),
            "status": flow_status,
            "version": "0.4.0-aligned",
            "source": "flow_events_jsonl",
            "kpis": {"latency": "streaming"},
        },
        "topology": topology,
        "traces": (
            traces[-tail_traces:] if tail_traces is not None and tail_traces > 0 else traces
        ),
        "message_log": (
            message_log[-tail_message_log:]
            if tail_message_log is not None and tail_message_log > 0
            else message_log
        ),
    }
    # File-based prompt/settings are included so the UI can display and edit real runtime config.
    # We also emit defaults for nodes missing from the file so the UI has a complete table.
    loaded = load_agent_prompt_settings()
    by_node = {p.node_id: p for p in loaded}

    # Only a subset of nodes actually consume LLM prompts/settings today.
    # Marking this explicitly prevents a misleading UI.
    llm_backed_actors = {
        "signal_arbitrator",
        "desk_debate",
        "portfolio_proposal",
        "portfolio_execute",
    }
    merged_rows: list[dict[str, Any]] = []
    for n in NODE_REGISTRY:
        nid = str(n.get("id") or "")
        actor = str(n.get("actor") or "")
        if not nid or not actor:
            continue
        applies = actor in llm_backed_actors
        base = by_node.get(nid).to_public_dict() if nid in by_node else None
        if base is None:
            label = str(n.get("label") or actor)
            base = AgentPromptSettings(
                node_id=nid,
                actor_id=actor,
                system_prompt=f"You are {label}. Produce compact, structured outputs. Never invent data; state assumptions.",
                task_prompt=f"For ticker {{ticker}} and run {{run_id}}: emit a {actor} summary.",
                cot_enabled=(actor in {"signal_arbitrator"}),
                tools=[],
            ).to_public_dict()
        merged_rows.append(
            {
                **base,
                "mode": "llm" if applies else "deterministic",
                "applies_to_runtime": applies,
            }
        )
    if merged_rows:
        payload["agent_prompts"] = merged_rows
    return payload, events
