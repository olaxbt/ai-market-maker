"""Pre-arbitration **desk debate**: two viewpoints appended to ``debate_transcript``.

1. **Deterministic** (always): macro/risk vs tape/alpha summaries from Tier-0 hooks — no API cost,
   visible in live flow events, backtest ``iterations.jsonl``, and downstream LLM arbitrator context.

2. **Optional LLM** (``AIMM_LLM_DESK_DEBATE=1`` when LLM arbitrator is on): two short model turns —
   Desk_Risk may call ``nexus.fetch_market_depth``; Desk_Tape is narrative-only (no tools) so operators
   see different tool access patterns in logs.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from config.agent_prompts import prompt_settings_by_actor
from config.llm_env import use_llm_arbitrator
from llm.openai_client import run_tool_calling_chat
from llm.tool_registry import nexus_tool_specs
from schemas.state import HedgeFundState
from workflow.arbitrator_shadow import legacy_deterministic_stance_preview
from workflow.tier2_context import bear_evidence_lines, bull_evidence_lines

logger = logging.getLogger(__name__)


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _normalize_debate_memo(text: str, *, max_chars: int) -> str:
    """Force a consistent debate memo format for UI + downstream arbitration.

    Keep only the first structured memo beginning at `Decision:` and
    trims anything after a clear second memo delimiter.
    """
    raw = (text or "").strip()
    if not raw:
        return "[empty model reply]"

    m = re.search(r"(?mi)^\s*Decision:\s*", raw)
    if m:
        raw = raw[m.start() :].lstrip()
    else:
        snippet = raw.replace("\n", " ").strip()
        if len(snippet) > 260:
            snippet = snippet[:260].rstrip() + "…"
        raw = (
            "Decision: HOLD (confidence=0.50)\n"
            "Evidence:\n"
            f"- Unstructured memo (format violation): {snippet}\n"
            "Risks:\n"
            "- Format violation reduces reliability.\n"
            "Would change mind if:\n"
            "- Desk resubmits in the required format.\n"
        )

    # Common drift patterns: a second memo starts, or markdown separators appear.
    cut_markers = [
        r"(?mi)^\s*\*\*Desk Memo:",
        r"(?mi)^\s*Desk Memo:",
        r"(?m)^\s*---\s*$",
    ]
    for pat in cut_markers:
        mm = re.search(pat, raw)
        if mm and mm.start() > 0:
            raw = raw[: mm.start()].rstrip()
            break

    if len(raw) > max_chars:
        raw = raw[:max_chars].rstrip() + "…"
    return raw


def _compact_context(state: HedgeFundState) -> str:
    tk = str(state.get("ticker") or "BTC/USDT")
    uni = state.get("universe")
    ulist = [str(x) for x in uni] if isinstance(uni, list) and uni else [tk]
    risk = state.get("risk") or {}
    ra = risk.get("analysis") if isinstance(risk.get("analysis"), dict) else {}
    # `risk.analysis[*].position_size` is suggested sizing (not current holdings).
    suggested_size = {
        s: {"suggested_position_size": (ra.get(s) or {}).get("position_size")}
        for s in ulist
        if isinstance(ra.get(s), dict)
    }
    sent = state.get("sentiment_analysis") or {}
    return json.dumps(
        {
            "ticker": tk,
            "universe": ulist,
            "sentiment_score": sent.get("sentiment_score") or sent.get("score"),
            "risk_suggested_position_size": suggested_size,
            "notes": {
                "risk_suggested_position_size": (
                    "This is suggested sizing from the risk desk, not current holdings/positions."
                )
            },
            "legacy_reference": legacy_deterministic_stance_preview(state),
        },
        default=str,
    )


def deterministic_debate_entries(state: HedgeFundState) -> list[dict[str, Any]]:
    bull = bull_evidence_lines(state)
    bear = bear_evidence_lines(state)
    ref = legacy_deterministic_stance_preview(state)
    risk_txt = "Risk-focused read (bear hooks / caution): " + (
        "; ".join(bear[:6]) if bear else "no strong bear Tier-0 hooks in this window."
    )
    tape_txt = "Tape-focused read (bull hooks / opportunity): " + (
        "; ".join(bull[:6]) if bull else "no strong bull Tier-0 hooks in this window."
    )
    ref_s = str(ref.get("stance") or "neutral")
    return [
        {
            "speaker": "desk_risk",
            "role": "macro_and_guardrails",
            "text": f"{risk_txt} | deterministic_reference_stance={ref_s}",
            "tools_available": [],
        },
        {
            "speaker": "desk_tape",
            "role": "technical_and_flow",
            "text": f"{tape_txt} | deterministic_reference_stance={ref_s}",
            "tools_available": [],
        },
    ]


def llm_desk_debate_entries(state: HedgeFundState) -> list[dict[str, Any]]:
    if not use_llm_arbitrator():
        return []
    if not _env_bool("AIMM_LLM_DESK_DEBATE", default=False):
        return []
    ctx = _compact_context(state)
    out: list[dict[str, Any]] = []
    ps = prompt_settings_by_actor().get("desk_debate")

    depth_specs = nexus_tool_specs(include_write_tools=False)
    if ps is not None and isinstance(ps.tools, list) and ps.tools:
        allow = {str(x) for x in ps.tools if str(x).strip()}
        depth_specs = [s for s in depth_specs if s.name in allow or s.wire_name in allow]
    sys_risk = (
        "You are Desk_Risk on a crypto fund.\n"
        "You must be concrete and decision-oriented. Use the provided JSON context; do not invent data.\n"
        "When you cite a fact, reference the JSON field name(s) you used (e.g. `legacy_reference`, "
        "`risk_position_size_scalar`, `sentiment_score`).\n"
        "If you need to verify a liquidity/depth claim and tools are available, you may call `nexus.fetch_market_depth` "
        "at most once.\n"
        "If a tool result is marked `is_mock=true` or `source=mock`, you MUST treat it as placeholder data and "
        "avoid strong conclusions based on it.\n"
        "Output format (strict, keep under 1400 chars):\n"
        "Decision: <BUY|SELL|HOLD> (confidence=<0.00-1.00>)\n"
        "Evidence:\n"
        "- <bullet 1 grounded in JSON, include field name>\n"
        "- <bullet 2 grounded in JSON, include field name>\n"
        "- <optional bullet 3 grounded in JSON, include field name>\n"
        "Risks:\n"
        "- <1-2 bullets>\n"
        "Would change mind if:\n"
        "- <1-2 bullets>\n"
        "Rules: no fluff, no repetition, no tables."
    )
    if ps is not None and (ps.system_prompt.strip() or ps.task_prompt.strip()):
        sys_risk = (
            sys_risk
            + "\n\nOperator prompt settings (apply to both desks):\n"
            + (ps.system_prompt.strip() or "")
            + ("\n\nTask:\n" + ps.task_prompt.strip() if ps.task_prompt.strip() else "")
        )
    try:
        text_r, ev_r = run_tool_calling_chat(
            system=sys_risk,
            user=ctx,
            tool_specs=depth_specs,
            model=(ps.model if ps is not None else None) or None,
            temperature=(ps.temperature if ps is not None else None),
            max_tokens=(ps.max_tokens if ps is not None else None),
            max_tool_rounds=2,
        )
        text_r = _normalize_debate_memo(text_r, max_chars=1400)
        if not text_r.lstrip().startswith("Decision:"):
            retry_sys = (
                sys_risk
                + "\n\nFORMAT ENFORCEMENT: Output ONLY the specified format. Do not add any other sections."
            )
            text_r2, ev_r2 = run_tool_calling_chat(
                system=retry_sys,
                user=ctx,
                tool_specs=depth_specs,
                model=(ps.model if ps is not None else None) or None,
                temperature=0.2 if (ps is None or ps.temperature is None) else ps.temperature,
                max_tokens=(ps.max_tokens if ps is not None else None),
                max_tool_rounds=2,
            )
            text_r2 = _normalize_debate_memo(text_r2, max_chars=1400)
            if text_r2.lstrip().startswith("Decision:"):
                text_r, ev_r = text_r2, ev_r2
        tools_used = sorted({str(e.get("name")) for e in ev_r if e.get("name")})
        out.append(
            {
                "speaker": "llm_desk_risk",
                "role": "llm_tools_depth",
                "text": text_r,
                "tools_available": [s.name for s in depth_specs],
                "tools_used": tools_used,
                "tool_events_count": len(ev_r),
            }
        )
    except Exception as e:
        logger.warning("LLM desk risk turn failed: %s", e)
        out.append(
            {
                "speaker": "llm_desk_risk",
                "role": "llm_tools_depth",
                "text": f"[llm_desk_risk error: {e}]",
                "tools_available": [s.name for s in depth_specs],
            }
        )

    sys_tape = (
        "You are Desk_Tape on a crypto fund.\n"
        "Focus on setup quality, momentum, and timing — when to lean vs wait — using only the JSON context.\n"
        "You do NOT have tools; do not pretend to have verified depth.\n"
        "When you cite a fact, reference the JSON field name(s) you used.\n"
        "Output format (strict, keep under 1200 chars):\n"
        "Decision: <BUY|SELL|HOLD> (confidence=<0.00-1.00>)\n"
        "Setup:\n"
        "- <2-3 bullets grounded in JSON, include field name>\n"
        "Timing:\n"
        "- <1-2 bullets>\n"
        "Invalidation:\n"
        "- <1-2 bullets>\n"
        "Rules: no fluff, no repetition, no tables."
    )
    if ps is not None and (ps.system_prompt.strip() or ps.task_prompt.strip()):
        sys_tape = (
            sys_tape
            + "\n\nOperator prompt settings (apply to both desks):\n"
            + (ps.system_prompt.strip() or "")
            + ("\n\nTask:\n" + ps.task_prompt.strip() if ps.task_prompt.strip() else "")
        )
    try:
        text_t, ev_t = run_tool_calling_chat(
            system=sys_tape,
            user=ctx,
            tool_specs=[],
            model=(ps.model if ps is not None else None) or None,
            temperature=(ps.temperature if ps is not None else None),
            max_tokens=(ps.max_tokens if ps is not None else None),
            max_tool_rounds=1,
        )
        text_t = _normalize_debate_memo(text_t, max_chars=1200)
        if not text_t.lstrip().startswith("Decision:"):
            retry_sys = (
                sys_tape
                + "\n\nFORMAT ENFORCEMENT: Output ONLY the specified format. Do not add any other sections."
            )
            text_t2, ev_t2 = run_tool_calling_chat(
                system=retry_sys,
                user=ctx,
                tool_specs=[],
                model=(ps.model if ps is not None else None) or None,
                temperature=0.2 if (ps is None or ps.temperature is None) else ps.temperature,
                max_tokens=(ps.max_tokens if ps is not None else None),
                max_tool_rounds=1,
            )
            text_t2 = _normalize_debate_memo(text_t2, max_chars=1200)
            if text_t2.lstrip().startswith("Decision:"):
                text_t, ev_t = text_t2, ev_t2
        out.append(
            {
                "speaker": "llm_desk_tape",
                "role": "llm_narrative_only",
                "text": text_t,
                "tools_available": [],
                "tools_used": [],
                "tool_events_count": len(ev_t),
            }
        )
    except Exception as e:
        logger.warning("LLM desk tape turn failed: %s", e)
        out.append(
            {
                "speaker": "llm_desk_tape",
                "role": "llm_narrative_only",
                "text": f"[llm_desk_tape error: {e}]",
                "tools_available": [],
            }
        )

    return out


def desk_debate(state: HedgeFundState) -> dict[str, Any]:
    """Graph node: append deterministic + optional LLM debate rows."""
    entries = deterministic_debate_entries(state)
    entries.extend(llm_desk_debate_entries(state))
    preview = []
    for row in entries:
        if not isinstance(row, dict):
            continue
        t = str(row.get("text") or "")
        if len(t) > 320:
            t = t[:320] + "…"
        preview.append(
            {
                "speaker": row.get("speaker"),
                "role": row.get("role"),
                "text": t,
                "tools_used": row.get("tools_used"),
            }
        )
    thought = (
        f"Desk debate: {len(entries)} entries "
        f"({sum(1 for e in entries if str(e.get('speaker', '')).startswith('llm_'))} LLM)."
    )
    include_full = _env_bool("AIMM_FLOW_INCLUDE_FULL_DEBATE", default=False)
    decision: dict[str, Any] = {"debate_preview": preview}
    if include_full:
        # Full transcript can be large; keep it opt-in for UI payload size.
        decision["debate_transcript"] = entries

    return {
        "debate_transcript": entries,
        "reasoning_logs": [
            {
                "node": "desk_debate",
                "reasoning_chain": thought,
                "thought_process": thought,
                "decision": decision,
                "extra": {
                    "debate_entry_count": len(entries),
                    "include_full_transcript": include_full,
                },
            }
        ],
    }


__all__ = ["desk_debate", "deterministic_debate_entries", "llm_desk_debate_entries"]
