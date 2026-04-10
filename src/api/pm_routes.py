"""PM / Executive summary endpoints for backtest runs.

These endpoints are designed for an always-on "exec agent" UI:
- Deterministic snapshot (fast, auditable)
- Optional LLM narrative on top (tool-calling not required)
"""

from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from adapters.nexus_adapter import get_nexus_adapter
from api.payload_adapter import build_nexus_payload
from backtest.exchange_trade_format import (
    trade_row_fee_usd,
    trade_row_side,
    trade_row_symbol_for_analytics,
)
from backtest.trade_book import read_jsonl_dict_records
from llm.openai_client import run_tool_calling_chat, stream_chat_completion

RUNS_DIR = Path(".runs")
BACKTESTS_DIR = RUNS_DIR / "backtests"
LATEST_RUN_FILE = RUNS_DIR / "latest_run.txt"

router = APIRouter(tags=["pm"])


@router.get("/pm/portfolio-health")
def get_portfolio_health() -> dict[str, Any]:
    """Live portfolio health (paper/live). Backtests use run artifacts under `.runs/backtests/`."""
    adapter = get_nexus_adapter()
    return adapter.get_portfolio_health()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    max_tokens: int = Field(450, ge=64, le=1500)


class AskResponse(BaseModel):
    run_id: str
    question: str
    answer: str
    model: str | None = None


def _sse(data: str) -> bytes:
    # SSE: each event is lines prefixed with "data:" and ends with a blank line.
    safe = (data or "").replace("\r", "")
    return ("".join([f"data: {line}\n" for line in safe.split("\n")]) + "\n").encode("utf-8")


def _extract_first_json_object(text: str) -> dict[str, Any] | None:
    """Best-effort: pull the first JSON object from a model response."""
    if not text:
        return None
    s = text.strip()
    start = s.find("{")
    if start < 0:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                frag = s[start : i + 1]
                try:
                    obj = json.loads(frag)
                except Exception:
                    return None
                return obj if isinstance(obj, dict) else None
    return None


def _resolve_backtest_dir(run_id: str) -> Path:
    rid = run_id
    if rid == "latest" and LATEST_RUN_FILE.exists():
        latest = LATEST_RUN_FILE.read_text().strip()
        if latest:
            rid = latest
    d = BACKTESTS_DIR / rid
    if not d.exists():
        raise HTTPException(status_code=404, detail=f"run not found: {rid}")
    return d


def _resolve_run_log(run_id: str) -> Path:
    rid = run_id
    if rid == "latest" and LATEST_RUN_FILE.exists():
        latest = LATEST_RUN_FILE.read_text().strip()
        if latest:
            rid = latest
    return RUNS_DIR / f"{rid}.events.jsonl"


def _is_stable_pair(sym: str) -> bool:
    s = (sym or "").upper()
    return any(
        x in s
        for x in (
            "USDC/USDT",
            "USD1/USDT",
            "FDUSD/USDT",
            "TUSD/USDT",
            "USDP/USDT",
        )
    )


def _build_snapshot(run_dir: Path, *, trades_limit: int = 5000) -> dict[str, Any]:
    summary_path = run_dir / "summary.json"
    trades_path = run_dir / "trades.jsonl"
    iterations_path = run_dir / "iterations.jsonl"
    if not summary_path.exists():
        raise HTTPException(status_code=404, detail=f"missing summary.json under {run_dir}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    bench = summary.get("benchmark") if isinstance(summary.get("benchmark"), dict) else {}

    trades = (
        read_jsonl_dict_records(trades_path, limit=trades_limit) if trades_path.exists() else []
    )
    iters = read_jsonl_dict_records(iterations_path, limit=2000) if iterations_path.exists() else []

    fee_total = 0.0
    side_ct: Counter[str] = Counter()
    sym_ct: Counter[str] = Counter()
    sym_fee: dict[str, float] = defaultdict(float)
    reason_cat: Counter[str] = Counter()
    forced = 0
    stable_trades = 0
    for tr in trades:
        sym = trade_row_symbol_for_analytics(tr)
        side = trade_row_side(tr)
        fee = trade_row_fee_usd(tr)
        fee_total += fee
        side_ct[side] += 1
        sym_ct[sym] += 1
        sym_fee[sym] += fee
        if _is_stable_pair(sym):
            stable_trades += 1
        meta = tr.get("_sim") if isinstance(tr.get("_sim"), dict) else {}
        legacy = tr.get("reason") if isinstance(tr.get("reason"), dict) else {}
        cat = str(meta.get("category") or legacy.get("category") or "")
        if cat:
            reason_cat[cat] += 1
            forced_by = str(meta.get("forced_by") or legacy.get("forced_by") or "")
            if forced_by == "backtest_engine":
                forced += 1

    intent_action = Counter()
    intent_conf: list[float] = []
    llm_any = False
    for it in iters:
        ti = it.get("trade_intent") if isinstance(it.get("trade_intent"), dict) else {}
        intent_action[str(ti.get("action") or "HOLD")] += 1
        c = ti.get("confidence")
        if isinstance(c, (int, float)):
            intent_conf.append(float(c))
        llm_any = bool(llm_any or it.get("llm_arbitrator") is True)

    avg_conf = (sum(intent_conf) / len(intent_conf)) if intent_conf else None
    steps_conf_ge_055 = sum(1 for x in intent_conf if x >= 0.55) if intent_conf else 0

    top_syms = [
        {"symbol": s, "fills": int(c), "fee_usd": round(float(sym_fee[s]), 2)}
        for s, c in sym_ct.most_common(10)
        if s
    ]

    snapshot = {
        "run_id": str(summary.get("run_id") or run_dir.name),
        "steps": summary.get("steps"),
        "trade_count": summary.get("trade_count"),
        "llm_arbitrator": llm_any,
        "returns": {
            "strategy_total_return_pct": bench.get("strategy_total_return_pct"),
            "btc_buy_hold_equity_return_pct": bench.get("benchmark_buy_hold_equity_return_pct"),
            "equal_weight_equity_return_pct": bench.get("benchmark_equal_weight_equity_return_pct"),
            "equal_weight_symbols": bench.get("benchmark_equal_weight_symbols"),
        },
        "fees": {
            "fees_usd_total": round(float(fee_total), 2),
        },
        "trading": {
            "sides": dict(side_ct),
            "stable_pair_trades": stable_trades,
            "stable_pair_trade_share": round(stable_trades / max(1, len(trades)), 4),
            "forced_exits": forced,
            "forced_exit_share": round(forced / max(1, len(trades)), 4),
            "top_reason_categories": dict(reason_cat.most_common(8)),
            "top_symbols_by_fills": top_syms,
        },
        "intent": {
            "actions_by_step": dict(intent_action),
            "confidence_avg": (round(avg_conf, 4) if avg_conf is not None else None),
            "steps_conf_ge_055": steps_conf_ge_055,
            "steps_with_conf": len(intent_conf),
        },
        "paths": summary.get("paths"),
    }
    return snapshot


def _llm_exec_summary(snapshot: dict[str, Any]) -> dict[str, Any]:
    system = (
        "You are the PM / Executive Summary agent for an algorithmic trading system.\n"
        "You must produce a concise, action-oriented status update about what happened in this run.\n"
        "Use ONLY the JSON snapshot provided; do not invent facts.\n"
        "Output valid JSON with keys: brief (list of strings), detail (string), risks (list of strings), next_actions (list of strings).\n"
        "Return JSON only (no markdown fences, no extra commentary).\n"
    )
    user = json.dumps(snapshot, indent=2, sort_keys=True)
    text, _tools = run_tool_calling_chat(system=system, user=user, tool_specs=[], max_tokens=900)
    try:
        out = json.loads(text)
        if isinstance(out, dict):
            return out
    except Exception:
        out2 = _extract_first_json_object(text)
        if isinstance(out2, dict):
            return out2
    return {
        "brief": ["llm_summary_parse_failed"],
        "detail": (text or "").strip()[:2000],
        "risks": [],
        "next_actions": [],
    }


def _llm_supervisor_answer(snapshot: dict[str, Any], *, question: str, max_tokens: int) -> str:
    system = (
        "You are the Supervisor for an agentic trading system.\n"
        "The user will ask a question about a specific backtest run.\n"
        "Use ONLY the JSON snapshot provided; do not invent facts.\n"
        "Answer concisely and actionably. If the snapshot lacks data, say what is missing.\n"
    )
    user = json.dumps({"snapshot": snapshot, "question": question}, indent=2, sort_keys=True)
    text, _tools = run_tool_calling_chat(
        system=system,
        user=user,
        tool_specs=[],
        max_tokens=max_tokens,
    )
    return (text or "").strip()[:4000]


def _build_run_snapshot(
    run_id: str, *, message_tail: int = 120, trace_tail: int = 60
) -> dict[str, Any]:
    """Snapshot for the *overall* system run (flow events → NexusPayload)."""
    log_path = _resolve_run_log(run_id)
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"run not found: {run_id}")
    payload, _events = build_nexus_payload(log_path)
    meta = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    topology = payload.get("topology") if isinstance(payload.get("topology"), dict) else {}
    nodes = topology.get("nodes") if isinstance(topology.get("nodes"), list) else []
    traces = payload.get("traces") if isinstance(payload.get("traces"), list) else []
    msg = payload.get("message_log") if isinstance(payload.get("message_log"), list) else []

    # Provide a "balance now" view for Supervisor even if the execution node hasn't emitted
    # a rich portfolio object yet. In paper mode this is a mock baseline.
    try:
        portfolio_health = get_nexus_adapter().get_portfolio_health()
    except Exception as e:
        portfolio_health = {"error": str(e)}

    return {
        "run_id": str(meta.get("run_id") or log_path.stem.replace(".events", "")),
        "ticker": meta.get("ticker"),
        "status": meta.get("status"),
        "portfolio_health": portfolio_health,
        "node_status": [
            {
                "id": n.get("id"),
                "actor": n.get("actor"),
                "label": n.get("label"),
                "status": n.get("status"),
                "summary": n.get("summary"),
            }
            for n in nodes
            if isinstance(n, dict)
        ],
        "counts": {
            "nodes": len(nodes),
            "traces": len(traces),
            "message_log": len(msg),
        },
        "recent": {
            "message_log": msg[-message_tail:],
            "traces": traces[-trace_tail:],
        },
    }


@router.get("/pm/backtests/{run_id}/snapshot")
def get_pm_snapshot(
    run_id: str,
    llm: bool = Query(
        False, description="If true and OPENAI_API_KEY is set, add LLM narrative summary."
    ),
) -> dict[str, Any]:
    run_dir = _resolve_backtest_dir(run_id)
    snap = _build_snapshot(run_dir)
    out: dict[str, Any] = {"snapshot": snap}
    if llm and os.getenv("OPENAI_API_KEY"):
        out["llm_summary"] = _llm_exec_summary(snap)
    return out


@router.post("/pm/backtests/{run_id}/ask", response_model=AskResponse)
def post_pm_ask(run_id: str, req: AskRequest) -> AskResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400, detail="OPENAI_API_KEY is not set (LLM supervisor disabled)."
        )
    run_dir = _resolve_backtest_dir(run_id)
    snap = _build_snapshot(run_dir)
    ans = _llm_supervisor_answer(snap, question=req.question, max_tokens=int(req.max_tokens))
    model = os.getenv("AIMM_LLM_MODEL") or os.getenv("OPENAI_MODEL") or None
    return AskResponse(
        run_id=str(snap.get("run_id") or run_id), question=req.question, answer=ans, model=model
    )


@router.get("/pm/runs/{run_id}/snapshot")
def get_pm_run_snapshot(
    run_id: str,
    llm: bool = Query(
        True, description="If true and OPENAI_API_KEY is set, add LLM narrative summary."
    ),
) -> dict[str, Any]:
    snap = _build_run_snapshot(run_id)
    out: dict[str, Any] = {"snapshot": snap}
    if llm and os.getenv("OPENAI_API_KEY"):
        out["llm_summary"] = _llm_exec_summary(snap)
    return out


@router.post("/pm/runs/{run_id}/ask", response_model=AskResponse)
def post_pm_run_ask(run_id: str, req: AskRequest) -> AskResponse:
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400, detail="OPENAI_API_KEY is not set (LLM supervisor disabled)."
        )
    snap = _build_run_snapshot(run_id)
    ans = _llm_supervisor_answer(snap, question=req.question, max_tokens=int(req.max_tokens))
    model = os.getenv("AIMM_LLM_MODEL") or os.getenv("OPENAI_MODEL") or None
    return AskResponse(
        run_id=str(snap.get("run_id") or run_id), question=req.question, answer=ans, model=model
    )


@router.post("/pm/runs/{run_id}/ask_stream")
def post_pm_run_ask_stream(run_id: str, req: AskRequest) -> StreamingResponse:
    """SSE stream for Supervisor chat (token-by-token)."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400, detail="OPENAI_API_KEY is not set (LLM supervisor disabled)."
        )
    snap = _build_run_snapshot(run_id)

    system = (
        "You are the Supervisor for an agentic trading system.\n"
        "The user will ask a question about the CURRENT system run.\n"
        "Use ONLY the JSON snapshot provided; do not invent facts.\n"
        "Answer concisely and actionably. If the snapshot lacks data, say what is missing.\n"
    )
    user = json.dumps({"snapshot": snap, "question": req.question}, indent=2, sort_keys=True)

    def gen():
        try:
            stream = stream_chat_completion(
                system=system,
                user=user,
                max_tokens=int(req.max_tokens),
            )
        except TypeError:
            # In case call signature changes; fall back to non-streaming.
            text, _ = run_tool_calling_chat(
                system=system,
                user=user,
                tool_specs=[],
                max_tokens=int(req.max_tokens),
            )
            yield _sse(text)
            yield _sse("[DONE]")
            return

        try:
            for ev in stream:
                try:
                    delta = ev.choices[0].delta
                    chunk = getattr(delta, "content", None)
                except Exception:
                    chunk = None
                if chunk:
                    yield _sse(str(chunk))
            yield _sse("[DONE]")
        except Exception as e:
            yield _sse(f"[ERROR] {e}")

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/pm/backtests/{run_id}/ask_stream")
def post_pm_backtest_ask_stream(run_id: str, req: AskRequest) -> StreamingResponse:
    """SSE stream for Supervisor chat (token-by-token) over a backtest snapshot."""
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(
            status_code=400, detail="OPENAI_API_KEY is not set (LLM supervisor disabled)."
        )
    run_dir = _resolve_backtest_dir(run_id)
    snap = _build_snapshot(run_dir)

    system = (
        "You are the Supervisor for an agentic trading system.\n"
        "The user will ask a question about a specific backtest run.\n"
        "Use ONLY the JSON snapshot provided; do not invent facts.\n"
        "Answer concisely and actionably. If the snapshot lacks data, say what is missing.\n"
    )
    user = json.dumps({"snapshot": snap, "question": req.question}, indent=2, sort_keys=True)

    def gen():
        try:
            stream = stream_chat_completion(
                system=system,
                user=user,
                max_tokens=int(req.max_tokens),
            )
        except TypeError:
            text, _ = run_tool_calling_chat(
                system=system,
                user=user,
                tool_specs=[],
                max_tokens=int(req.max_tokens),
            )
            yield _sse(text)
            yield _sse("[DONE]")
            return

        try:
            for ev in stream:
                try:
                    delta = ev.choices[0].delta
                    chunk = getattr(delta, "content", None)
                except Exception:
                    chunk = None
                if chunk:
                    yield _sse(str(chunk))
            yield _sse("[DONE]")
        except Exception as e:
            yield _sse(f"[ERROR] {e}")

    return StreamingResponse(gen(), media_type="text/event-stream")
