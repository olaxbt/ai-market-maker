from __future__ import annotations

import json
from typing import Any

from config.agent_prompts import prompt_settings_by_actor
from llm.json_parse import parse_json_object
from llm.openai_client import run_tool_calling_chat
from llm.structured_output import (
    clamp_int,
    llm_output_retries,
    llm_strict_json_enabled,
    strict_json_suffix,
)
from schemas.state import HedgeFundState


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


def _strict_json_suffix_portfolio() -> str:
    return strict_json_suffix(
        keys=("trades",),
        extra_rules=(
            "- Required top-level key: trades.",
            "- trades must be an object keyed by symbol.",
            "- For each symbol in universe, include an object with: action (buy|sell|hold).",
            "- Optional keys per symbol: weight (0..1), amount (>0), stop_price (>0).",
            "- Do not include symbols outside universe.",
        ),
    )


def _needs_retry_portfolio(proposal: dict[str, Any], *, universe: list[str]) -> bool:
    # Retry if the model didn't provide trades for any universe symbol.
    if not isinstance(proposal, dict):
        return True
    if proposal.get("status") != "success":
        return True
    trades = proposal.get("trades")
    if not isinstance(trades, dict):
        return True
    # If everything got filtered out, it's almost certainly a format issue.
    if len(trades) == 0 and len(universe) > 0:
        return True
    return False


def _strict_json_suffix_execute() -> str:
    return strict_json_suffix(
        keys=("smart_orders",),
        extra_rules=(
            "- Required top-level key: smart_orders.",
            "- smart_orders must be a JSON array.",
            '- Each item: {"symbol": string, "side": "buy"|"sell", "qty": number}.',
            "- Only include symbols in universe.",
            "- qty must be > 0.",
            "- If trade_intent.action is BUY or SELL, include at least one small order unless risk forbids it.",
        ),
    )


def _sanitize_smart_orders(
    parsed: dict[str, Any] | None, *, universe: list[str]
) -> list[dict[str, Any]]:
    parsed = parsed if isinstance(parsed, dict) else {}
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
    return cleaned


def _needs_retry_execute(cleaned: list[dict[str, Any]], *, universe: list[str]) -> bool:
    # Execute step is allowed to be a no-op; only retry when output is malformed (i.e. parse produced nothing
    # but the model likely intended orders).
    # Heuristic: if the universe is non-empty and we got no cleaned orders, do NOT retry by default.
    # Operators can raise retries if their model frequently emits malformed arrays.
    return False


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

    retries = clamp_int(llm_output_retries(), lo=0, hi=5)
    strict_json = llm_strict_json_enabled()
    attempts = 0
    retry_reasons: list[str] = []
    last_text = ""
    tool_events: list[dict[str, Any]] = []
    proposal: dict[str, Any] = {"status": "error", "message": "uninitialized", "trades": {}}

    base_system = system + "\n\n" + task + (_strict_json_suffix_portfolio() if strict_json else "")
    for attempt in range(retries + 1):
        attempts = attempt + 1
        sys_prompt = base_system
        if attempt > 0:
            sys_prompt = (
                sys_prompt
                + "\n\nRETRY:\n"
                + "Your previous output failed validation. Fix it and return ONLY the JSON object."
            )
        try:
            text, tool_events = run_tool_calling_chat(
                system=sys_prompt,
                user=user,
                tool_specs=[],
                model=(ps.model if ps is not None else None),
                temperature=(ps.temperature if ps is not None else None),
                max_tokens=(ps.max_tokens if ps is not None else None),
            )
            last_text = text or ""
        except Exception as exc:
            proposal = {
                "status": "error",
                "message": f"llm_error:{type(exc).__name__}",
                "trades": {},
            }
            retry_reasons.append(proposal["message"])
            continue

        parsed = parse_json_object(last_text)
        proposal = sanitize_portfolio_trades(parsed, universe=universe)
        if _needs_retry_portfolio(proposal, universe=universe):
            retry_reasons.append(str(proposal.get("message") or "invalid_portfolio_output"))
            continue
        break

    proposal["llm_tool_events"] = tool_events
    proposal["llm_attempts"] = attempts
    proposal["llm_retry_reasons"] = retry_reasons[:5]
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
            "Only include symbols in universe. Use small quantities.\n"
            "- If trade_intent.action is BUY or SELL, you SHOULD return at least one small smart_order.\n"
            "- Use paper.cash_usdt and paper.positions to avoid oversizing.\n"
            "- Prefer no-op only when trade_intent is HOLD or when constrained by risk/uncertainty."
        )
    )
    sm = state.get("shared_memory") or {}
    paper = sm.get("paper") if isinstance(sm, dict) and isinstance(sm.get("paper"), dict) else {}
    user = json.dumps(
        {
            "ticker": tk,
            "universe": universe,
            "portfolio_result": portfolio_result,
            "risk": state.get("risk") or {},
            "paper": paper,
            "trade_intent": state.get("trade_intent") or {},
            "prices": state.get("market_data") or {},
        },
        default=str,
    )
    retries = clamp_int(llm_output_retries(), lo=0, hi=5)
    strict_json = llm_strict_json_enabled()
    attempts = 0
    retry_reasons: list[str] = []
    tool_events: list[dict[str, Any]] = []
    cleaned: list[dict[str, Any]] = []

    base_system = system + "\n\n" + task + (_strict_json_suffix_execute() if strict_json else "")
    for attempt in range(retries + 1):
        attempts = attempt + 1
        sys_prompt = base_system
        if attempt > 0:
            sys_prompt = (
                sys_prompt
                + "\n\nRETRY:\n"
                + "Your previous output failed validation. Fix it and return ONLY the JSON object."
            )
        try:
            text, tool_events = run_tool_calling_chat(
                system=sys_prompt,
                user=user,
                tool_specs=[],
                model=(ps.model if ps is not None else None),
                temperature=(ps.temperature if ps is not None else None),
                max_tokens=(ps.max_tokens if ps is not None else None),
            )
        except Exception as exc:
            retry_reasons.append(f"llm_error:{type(exc).__name__}")
            continue
        parsed = parse_json_object(text)
        cleaned = _sanitize_smart_orders(parsed, universe=universe)
        if _needs_retry_execute(cleaned, universe=universe):
            retry_reasons.append("invalid_smart_orders")
            continue
        break

    return {
        "status": "executed" if cleaned else "skipped",
        "smart_orders": cleaned,
        "llm_tool_events": tool_events,
        "llm_attempts": attempts,
        "llm_retry_reasons": retry_reasons[:5],
    }


__all__ = ["llm_portfolio_execute", "llm_portfolio_proposal", "sanitize_portfolio_trades"]
