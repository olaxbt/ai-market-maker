from __future__ import annotations

import json
import os
from typing import Any, Dict

from llm.openai_client import run_tool_calling_chat
from llm.tool_registry import nexus_tool_specs
from schemas.state import HedgeFundState


def _reasoning_entry(
    *,
    node: str,
    thought: str,
    decision: Any | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    detail = thought.strip() if isinstance(thought, str) else str(thought)
    return {
        "node": node,
        "reasoning_chain": detail,
        "thought_process": detail,
        "decision": decision,
        "extra": extra or {},
    }


def _env_bool(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def signal_arbitrator_llm(state: HedgeFundState) -> Dict[str, Any]:
    """Tier-2 synthesis node driven by an LLM with tool-calling enabled.

    Gated behind `AI_MARKET_MAKER_USE_LLM=1`.
    """
    if not _env_bool("AI_MARKET_MAKER_USE_LLM", False):
        raise RuntimeError("signal_arbitrator_llm called but AI_MARKET_MAKER_USE_LLM is disabled")

    ticker = str(state.get("ticker") or "BTC/USDT")
    transcript = state.get("debate_transcript") or []
    risk = state.get("risk") or {}
    sentiment = state.get("sentiment_analysis") or {}

    system = (
        "You are the Signal Arbitrator in a hedge-fund multi-agent system.\n"
        "Synthesize bull/bear debate plus risk/sentiment into a single proposed_signal.\n"
        "If you need market microstructure context, call nexus.fetch_market_depth.\n"
        "Output MUST be valid JSON with keys: stance, confidence, reasons (array of strings).\n"
        "Stance must be one of: bullish, bearish, neutral."
    )
    user = json.dumps(
        {
            "ticker": ticker,
            "debate_transcript": transcript,
            "risk": risk,
            "sentiment": sentiment,
        },
        indent=2,
        sort_keys=True,
    )

    specs = nexus_tool_specs(include_write_tools=False)
    text, tool_events = run_tool_calling_chat(system=system, user=user, tool_specs=specs)

    parsed: Dict[str, Any] = {}
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = {"stance": "neutral", "confidence": 0.5, "reasons": ["llm_output_parse_failed"]}

    stance = (
        parsed.get("stance")
        if parsed.get("stance") in ("bullish", "bearish", "neutral")
        else "neutral"
    )
    confidence = parsed.get("confidence")
    try:
        confidence_f = float(confidence)
    except Exception:
        confidence_f = 0.5
    confidence_f = max(0.0, min(0.95, confidence_f))
    reasons = parsed.get("reasons")
    if not isinstance(reasons, list):
        reasons = []
    reasons = [str(r) for r in reasons][:12]

    proposed_signal = {
        "action": "PROPOSAL",
        "params": {
            "stance": stance,
            "confidence": round(confidence_f, 2),
            "reasons": reasons,
            "tool_events": tool_events,
            "debate_entries": len(transcript),
        },
        "meta": {"source": "signal_arbitrator_llm", "model": os.getenv("OPENAI_MODEL")},
    }

    reasoning_logs = [
        _reasoning_entry(
            # Keep the canonical node id so topology + UI grouping work.
            node="signal_arbitrator",
            thought="LLM synthesized debate into proposed_signal (tool-calling enabled).",
            decision=proposed_signal,
            extra={"tool_events_count": len(tool_events), "llm": True},
        )
    ]

    # Emit one reasoning entry per tool call so the Event Stream shows tool activity.
    for ev in tool_events:
        name = str(ev.get("name") or ev.get("wire_name") or "tool")
        args = ev.get("args") or {}
        result = ev.get("result") or {}
        # Keep the thought compact for the stream; full args/result are in extra/decision.
        reasoning_logs.append(
            _reasoning_entry(
                node="signal_arbitrator",
                thought=f"Tool call: {name}",
                decision=result,
                extra={
                    "tool_name": name,
                    "tool_args": args,
                    "wire_name": ev.get("wire_name"),
                    "llm": True,
                },
            )
        )

    return {
        "proposed_signal": proposed_signal,
        "reasoning_logs": reasoning_logs,
    }


__all__ = ["signal_arbitrator_llm"]
