from __future__ import annotations

import json
from typing import Any

from config.agent_prompts import prompt_settings_by_actor
from llm.openai_client import run_tool_calling_chat
from schemas.state import HedgeFundState


def _parse_llm_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    if "```" in raw:
        for block in raw.split("```"):
            chunk = block.strip()
            if chunk.lower().startswith("json"):
                chunk = chunk[4:].lstrip()
            if chunk.startswith("{"):
                raw = chunk
                break
    try:
        out = json.loads(raw)
        return out if isinstance(out, dict) else None
    except Exception:
        pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            out = json.loads(raw[start : end + 1])
            return out if isinstance(out, dict) else None
        except Exception:
            return None
    return None


def sanitize_portfolio_trades(
    parsed: dict[str, Any] | None, *, universe: list[str]
) -> dict[str, Any]:
    """Return a canonical portfolio proposal dict compatible with existing execution code."""
    out: dict[str, Any] = {"status": "success", "trades": {}}
    if not isinstance(parsed, dict):
        out["status"] = "error"
        out["message"] = "llm_output_not_json_object"
        return out
    trades = parsed.get("trades")
    if not isinstance(trades, dict):
        out["status"] = "error"
        out["message"] = "missing_trades"
        return out
    cleaned: dict[str, Any] = {}
    for sym in universe:
        row = trades.get(sym)
        if not isinstance(row, dict):
            continue
        action = str(row.get("action") or "").strip().lower()
        if action not in {"buy", "sell", "hold"}:
            continue
        cleaned[sym] = {
            "action": action,
            # optional fields
            **(
                {
                    k: row[k]
                    for k in ("weight", "amount", "stop_price")
                    if k in row and row[k] is not None
                }
            ),
        }
    out["trades"] = cleaned
    # Preserve extra metadata if present
    if isinstance(parsed.get("meta"), dict):
        out["meta"] = parsed["meta"]
    return out


def llm_portfolio_proposal(state: HedgeFundState) -> dict[str, Any]:
    tk = str(state.get("ticker") or "BTC/USDT")
    uni = state.get("universe")
    universe = [str(x) for x in uni] if isinstance(uni, list) and uni else [tk]

    ps = prompt_settings_by_actor().get("portfolio_proposal")
    system = (
        ps.system_prompt.strip()
        if ps and ps.system_prompt.strip()
        else "You are the Portfolio Proposal desk for a crypto fund."
    )
    task = (
        ps.task_prompt.strip()
        if ps and ps.task_prompt.strip()
        else (
            'Return JSON {"trades": {SYMBOL: {"action": "buy|sell|hold", "weight": number}}}.\n'
            "Only include symbols from universe. Prefer HOLD unless confidence is strong."
        )
    )
    user = json.dumps(
        {
            "ticker": tk,
            "universe": universe,
            "proposed_signal": state.get("proposed_signal") or {},
            "trade_intent": state.get("trade_intent") or {},
            "risk": state.get("risk") or {},
            "sentiment": state.get("sentiment_analysis") or {},
            "quant": state.get("quant_analysis") or {},
        },
        default=str,
    )

    try:
        text, tool_events = run_tool_calling_chat(
            system=system + "\n\n" + task,
            user=user,
            tool_specs=[],
            model=(ps.model if ps is not None else None),
            temperature=(ps.temperature if ps is not None else None),
            max_tokens=(ps.max_tokens if ps is not None else None),
        )
    except Exception as exc:
        # Never crash the trading loop on provider/model misconfig.
        return {
            "status": "error",
            "message": f"llm_error:{type(exc).__name__}",
            "trades": {},
        }
    parsed = _parse_llm_json_object(text)
    proposal = sanitize_portfolio_trades(parsed, universe=universe)
    proposal["llm_tool_events"] = tool_events
    return proposal


def llm_portfolio_execute(
    state: HedgeFundState, *, portfolio_result: dict[str, Any]
) -> dict[str, Any]:
    tk = str(state.get("ticker") or "BTC/USDT")
    uni = state.get("universe")
    universe = [str(x) for x in uni] if isinstance(uni, list) and uni else [tk]

    ps = prompt_settings_by_actor().get("portfolio_execute")
    system = (
        ps.system_prompt.strip()
        if ps and ps.system_prompt.strip()
        else "You are the Execution desk. Produce a conservative execution plan."
    )
    task = (
        ps.task_prompt.strip()
        if ps and ps.task_prompt.strip()
        else (
            'Return JSON {"smart_orders": [{"symbol": str, "side": "buy|sell", "qty": number}] }.\n'
            "Only include symbols in universe. Use small quantities. Prefer no-op if unclear."
        )
    )
    user = json.dumps(
        {
            "ticker": tk,
            "universe": universe,
            "portfolio_result": portfolio_result,
            "risk": state.get("risk") or {},
        },
        default=str,
    )
    try:
        text, tool_events = run_tool_calling_chat(
            system=system + "\n\n" + task,
            user=user,
            tool_specs=[],
            model=(ps.model if ps is not None else None),
            temperature=(ps.temperature if ps is not None else None),
            max_tokens=(ps.max_tokens if ps is not None else None),
        )
    except Exception as exc:
        return {
            "status": "skipped",
            "message": f"llm_error:{type(exc).__name__}",
            "smart_orders": [],
        }
    parsed = _parse_llm_json_object(text) or {}
    smart_orders = parsed.get("smart_orders")
    if not isinstance(smart_orders, list):
        smart_orders = []
    cleaned: list[dict[str, Any]] = []
    for row in smart_orders:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or "")
        side = str(row.get("side") or "").lower()
        try:
            qty = float(row.get("qty") or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if sym not in universe or side not in {"buy", "sell"} or qty <= 0:
            continue
        cleaned.append({"symbol": sym, "side": side, "qty": qty})
    return {
        "status": "executed" if cleaned else "skipped",
        "smart_orders": cleaned,
        "llm_tool_events": tool_events,
    }


__all__ = ["llm_portfolio_execute", "llm_portfolio_proposal", "sanitize_portfolio_trades"]
