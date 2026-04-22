from __future__ import annotations

import json
import os
from typing import Any, Dict

from config.agent_prompts import prompt_settings_by_actor
from config.llm_env import use_llm_arbitrator
from llm.json_parse import parse_json_object
from llm.openai_client import run_tool_calling_chat
from llm.structured_output import (
    clamp_int,
    llm_output_retries,
    llm_strict_json_enabled,
    strict_json_suffix,
)
from llm.tool_registry import nexus_tool_specs
from schemas.state import HedgeFundState
from tier1 import apply_strategy, effective_portfolio_desk_bridge, load_tier1_blueprint_from_env
from tier1.signal_params import build_tier1_proposed_params
from trading.desk_inputs import quant_analysis_for_portfolio
from workflow.arbitrator_shadow import (
    backtest_momentum_score_delta,
    legacy_deterministic_stance_preview,
)
from workflow.execution_intent import derive_trade_intent
from workflow.tier2_context import (
    bear_evidence_lines,
    build_synthesis_board,
    bull_evidence_lines,
    compact_tier0_for_prompt,
    compute_legacy_arbitrator_scores,
)


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


def sanitize_llm_arbitrator_output(
    parsed: Dict[str, Any] | None,
) -> tuple[Dict[str, Any], list[str]]:
    """Validate / coerce LLM JSON into arbitrator fields; return canonical dict + warning tags."""
    warnings: list[str] = []
    if not isinstance(parsed, dict):
        return {
            "stance": "neutral",
            "confidence": 0.5,
            "reasons": ["llm_output_not_json_object"],
        }, ["invalid_payload"]

    stance_raw = parsed.get("stance")
    if stance_raw not in ("bullish", "bearish", "neutral"):
        warnings.append(f"stance_coerced_invalid:{stance_raw!r}")
        stance = "neutral"
    else:
        stance = str(stance_raw)

    try:
        confidence_f = float(parsed.get("confidence"))
    except (TypeError, ValueError):
        warnings.append("confidence_coerced_non_numeric")
        confidence_f = 0.5
    if confidence_f < 0.0 or confidence_f > 0.95:
        warnings.append("confidence_clamped_to_0_95")
    confidence_f = max(0.0, min(0.95, confidence_f))

    reasons = parsed.get("reasons")
    if not isinstance(reasons, list):
        warnings.append("reasons_coerced_non_list")
        reasons = []
    reasons_out = [str(r) for r in reasons][:12]

    return (
        {
            "stance": stance,
            "confidence": round(confidence_f, 4),
            "reasons": reasons_out,
        },
        warnings,
    )


def _needs_retry(parse_ok: bool, warnings: list[str]) -> bool:
    """Heuristic: retry when output isn't parseable or was heavily coerced."""
    if not parse_ok:
        return True
    bad_prefixes = (
        "invalid_payload",
        "json_parse_failed",
        "stance_coerced_invalid",
        "confidence_coerced_non_numeric",
        "reasons_coerced_non_list",
    )
    return any(any(w == bp or w.startswith(bp + ":") for bp in bad_prefixes) for w in warnings)


def _strict_json_suffix() -> str:
    return strict_json_suffix(
        keys=("stance", "confidence", "reasons"),
        extra_rules=(
            "- stance MUST be one of: bullish | bearish | neutral.",
            "- confidence MUST be a number in [0.0, 0.95].",
            "- reasons MUST be an array of 3-8 short strings.",
        ),
    )


def _backtest_prompt_context(state: HedgeFundState, *, ticker: str) -> dict[str, Any]:
    """Compact facts so the model does not confuse risk sizing with sim position or ignore tape drift."""
    md = state.get("market_data") or {}
    row = md.get(ticker) if isinstance(md.get(ticker), dict) else {}
    ohlcv = row.get("ohlcv") if isinstance(row.get("ohlcv"), list) else []
    ctx: dict[str, Any] = {"primary_ohlcv_rows": len(ohlcv)}
    if len(ohlcv) >= 2:
        try:
            c0 = float(ohlcv[0][4])
            c1 = float(ohlcv[-1][4])
            if c0 > 0:
                ctx["window_close_to_close_return_pct"] = round((c1 / c0 - 1.0) * 100.0, 4)
        except (TypeError, ValueError, IndexError):
            pass
    sm = state.get("shared_memory") if isinstance(state.get("shared_memory"), dict) else {}
    bt = sm.get("backtest") if isinstance(sm.get("backtest"), dict) else {}
    if bt:
        ctx["sim_cash_usd"] = float(bt.get("cash", 0.0) or 0.0)
        pos = bt.get("positions")
        if isinstance(pos, dict):
            ctx["sim_qty_by_symbol"] = {str(k): float(v) for k, v in pos.items()}
        else:
            ctx["sim_qty_base"] = float(bt.get("qty", 0.0) or 0.0)
    return ctx


def signal_arbitrator_llm(state: HedgeFundState) -> Dict[str, Any]:
    """Tier-2 synthesis node driven by an LLM with tool-calling enabled.

    Gated behind `AI_MARKET_MAKER_USE_LLM=1`.
    """
    if not use_llm_arbitrator():
        raise RuntimeError("signal_arbitrator_llm called but AI_MARKET_MAKER_USE_LLM is disabled")

    ticker = str(state.get("ticker") or "BTC/USDT")
    transcript = state.get("debate_transcript") or []
    risk = state.get("risk") or {}
    sentiment = state.get("sentiment_analysis") or {}

    legacy = compute_legacy_arbitrator_scores(state)
    tc = legacy["tier0_consensus"]
    tier0_compact = compact_tier0_for_prompt(state)
    legacy_preview = legacy_deterministic_stance_preview(state)

    qa = quant_analysis_for_portfolio(state, ticker, desk_bridge=effective_portfolio_desk_bridge())
    q_analysis = qa.get("analysis") if isinstance(qa.get("analysis"), dict) else {}
    q_tick = q_analysis.get(ticker, {}) if isinstance(q_analysis.get(ticker), dict) else {}
    quant_desk_bridge = {
        k: q_tick[k] for k in ("macd_signal", "desk_sources", "desk_strategy_preset") if k in q_tick
    }

    tier1_deterministic: dict[str, Any] | None = None
    ep = None
    bp = load_tier1_blueprint_from_env()
    if bp is not None:
        ep = apply_strategy(state, bp, ticker=ticker)
        tier1_deterministic = ep.model_dump(mode="json")

    mb, ms, _mn = backtest_momentum_score_delta(state)
    bull_adj = int(legacy["bull_score"]) + mb
    bear_adj = int(legacy["bear_score"]) + ms
    reference_kind: str
    if ep is not None:
        pr_ref = build_tier1_proposed_params(
            ep,
            tier0_summary=str(tc.get("summary", "")),
            legacy_bull_score=bull_adj,
            legacy_bear_score=bear_adj,
        )
        reference_stance = str(pr_ref.get("stance") or "neutral")
        reference_kind = "tier1_applier"
    else:
        reference_stance = str(legacy_preview.get("stance") or "neutral")
        reference_kind = "legacy_scores"

    deterministic_reference = {
        "reference_stance": reference_stance,
        "reference_kind": reference_kind,
        "legacy_score_path": legacy_preview,
        "quant_desk_bridge": quant_desk_bridge,
    }

    bull_hooks = bull_evidence_lines(state)
    bear_hooks = bear_evidence_lines(state)

    system = (
        "You are the Signal Arbitrator in a hedge-fund multi-agent system.\n"
        "A **desk_debate** step ran before you: ``debate_transcript`` contains deterministic macro vs tape views "
        "and, when enabled, two short LLM desk turns (risk may use depth tools; tape is narrative-only). "
        "Use it as structured disagreement, not as a second secret state.\n"
        "You receive: (1) debate_transcript, (2) risk and sentiment, "
        "(3) tier0_contracts_compact — per-agent Tier-0 JSON scalars, "
        "(4) tier0_bull_hooks / tier0_bear_hooks — short pro/con lines derived from those contracts, "
        "(5) tier0_consensus — pre-aggregated tilts, "
        "(6) legacy_arbitrator_scores — score engine when Tier-1 blueprint is off, "
        "(7) tier1_deterministic_execution — if non-null, deterministic Tier-1 applier output, "
        "(8) deterministic_reference — legacy score path + quant_desk_bridge (TA/stat alpha → buy/sell/hold for the portfolio desk), "
        "(9) backtest_prompt_context — sim cash/qty and cumulative window return on the primary pair.\n"
        "Multi-asset: if the user payload includes ``universe`` with multiple tickers, the portfolio desk splits risk "
        "budget across those symbols; execution may emit one smart order per symbol with a proposed fill. Your stance "
        "still guides trade_intent for the **primary** ticker, but bullish + sufficient confidence helps the whole book.\n"
        "Churn guard (important): This backtest sim is sensitive to flip-flopping because it can generate many small "
        "adds/exits with fees. Prefer **neutral** with confidence < 0.55 when evidence is mixed or weak. Only switch "
        'from bullish↔bearish when the pro/con evidence changes materially. If you are unsure, do not "force action".\n'
        "Stablecoin sanity: If the universe contains stable/stable-ish pairs (e.g. USDC/USDT, USD1/USDT), do not let "
        "them drive an aggressive bullish/bearish stance; they are low-vol and mostly noise. Focus on the primary "
        "ticker and the non-stable high-beta legs for directional thesis.\n"
        "Alignment gating: You should only output confidence >= 0.55 (directional intent) when at least one of these "
        "is true:\n"
        "- (A) quant_desk_snapshot.macd_signal == buy AND deterministic_reference.reference_stance == bullish, OR\n"
        "- (B) tier1_deterministic_execution is present with conviction_score >= 70 AND backtest_prompt_context.window_close_to_close_return_pct is > 0.\n"
        "If quant is sell and Tier-1 is long, default to neutral with confidence <= 0.54 unless (B) is satisfied.\n"
        "Risk JSON semantics: risk.analysis[ticker].position_size is a **risk-budget / sizing scalar for the allocator**, "
        "NOT an open position in base coin. The simulated book is in backtest_prompt_context (sim_cash_usd, sim_qty_base "
        "or sim_qty_by_symbol). Never infer a huge BTC position from risk.analysis alone.\n"
        'Quant / MACD warmup: macd_signal "hold" with empty or sparse desk_sources often means **insufficient bars** '
        "for MACD, not a bearish veto. If the active Tier-1 blueprint enables ``Portfolio_Desk_Bridge.Close_Momentum_When_TA_Hold``, "
        "the desk may emit **buy** with ``close_momentum`` in desk_sources when OHLCV drift is positive; otherwise treat hold "
        "at face value. If the desk stays hold, still weigh deterministic_reference.reference_stance — if **bullish** and hooks "
        "are not materially bearish, prefer **bullish** with confidence high enough for downstream BUY intent (>=0.55) rather "
        "than defaulting to neutral — unless quant_desk_bridge.macd_signal is explicitly **sell** or "
        "tier0_consensus.block_aggressive_long is true.\n"
        "Policy: When tier1_deterministic_execution is non-null, prefer alignment with its implied stance "
        "(same as deterministic_reference.reference_stance) unless quant_desk_bridge or risk clearly contradicts; "
        "if you disagree, state that in reasons[]. When Tier-1 is null, weigh deterministic_reference.reference_stance "
        "(legacy bull/bear + backtest momentum) against hooks and risk.\n"
        "Quant accountability: include the string quant_desk= in at least one reasons[] entry, giving "
        'macd_signal and desk_sources (e.g. "quant_desk=buy:[technical_ta_engine]" or hold:[]).\n'
        "Also include churn_guard= in at least one reasons[] entry, briefly stating why you are (or are not) "
        "high-confidence enough to cross 0.55.\n"
        "Also include alignment_gate= in at least one reasons[] entry, stating whether you met (A) or (B), or why you didn't.\n"
        "If you need more microstructure, call nexus.fetch_market_depth.\n"
        "Output MUST be valid JSON with keys: stance, confidence, reasons (array of strings).\n"
        "Stance must be one of: bullish, bearish, neutral."
    )
    # Operator-configurable (file-based) overrides.
    ps = prompt_settings_by_actor().get("signal_arbitrator")
    if ps is not None:
        if ps.system_prompt.strip():
            system = ps.system_prompt.strip()
        if ps.task_prompt.strip():
            system = system.rstrip() + "\n\nOperator task prompt:\n" + ps.task_prompt.strip()
    uni = state.get("universe")
    universe_out = [str(x) for x in uni] if isinstance(uni, list) and uni else [ticker]
    user = json.dumps(
        {
            "ticker": ticker,
            "universe": universe_out,
            "debate_transcript": transcript,
            "backtest_prompt_context": _backtest_prompt_context(state, ticker=ticker),
            "deterministic_reference": deterministic_reference,
            "tier0_bull_hooks": bull_hooks,
            "tier0_bear_hooks": bear_hooks,
            "risk": risk,
            "sentiment": sentiment,
            "tier0_contracts_compact": tier0_compact,
            "tier0_consensus": {
                "bull_tilt": tc.get("bull_tilt"),
                "bear_tilt": tc.get("bear_tilt"),
                "block_aggressive_long": tc.get("block_aggressive_long"),
                "summary": tc.get("summary"),
                "parts": tc.get("parts"),
            },
            "legacy_arbitrator_scores": {
                "bull_score": legacy["bull_score"],
                "bear_score": legacy["bear_score"],
                "bull_votes": legacy["bull_votes"],
                "bear_votes": legacy["bear_votes"],
                "high_vol_assets": legacy["high_vol_assets"],
                "sentiment_score": legacy["sentiment_score"],
            },
            "tier1_deterministic_execution": tier1_deterministic,
        },
        indent=2,
        sort_keys=True,
    )

    specs = nexus_tool_specs(include_write_tools=False)
    if ps is not None and isinstance(ps.tools, list) and ps.tools:
        allow = {str(x) for x in ps.tools if str(x).strip()}
        specs = [s for s in specs if s.name in allow or s.wire_name in allow]
    model_name = (
        (ps.model if ps is not None else None) or os.getenv("OPENAI_MODEL") or "gpt-4o-mini"
    )
    retries = clamp_int(llm_output_retries(), lo=0, hi=5)
    strict_json = llm_strict_json_enabled()
    last_text = ""
    tool_events: list[dict[str, Any]] = []
    parse_ok = False
    parsed_raw: dict[str, Any] | None = None
    canonical: dict[str, Any] = {
        "stance": "neutral",
        "confidence": 0.5,
        "reasons": ["llm_uninitialized"],
    }
    val_warnings: list[str] = ["uninitialized"]
    attempts = 0
    retry_reasons: list[str] = []

    for attempt in range(retries + 1):
        attempts = attempt + 1
        sys_prompt = system + (_strict_json_suffix() if strict_json else "")
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
                tool_specs=specs,
                model=model_name,
                temperature=(ps.temperature if ps is not None else None),
                max_tokens=(ps.max_tokens if ps is not None else None),
            )
            last_text = text or ""
        except Exception as exc:
            # Runs should continue even if the provider stalls or errors.
            last_text = json.dumps(
                {
                    "stance": "neutral",
                    "confidence": 0.5,
                    "reasons": [f"llm_error_fallback:{type(exc).__name__}"],
                }
            )
            tool_events = [
                {
                    "name": "llm_error_fallback",
                    "wire_name": "llm_error_fallback",
                    "args": {},
                    "result": {"error": f"{type(exc).__name__}: {exc}"},
                }
            ]

        parsed_raw = parse_json_object(last_text)
        parse_ok = parsed_raw is not None
        canonical, val_warnings = sanitize_llm_arbitrator_output(parsed_raw)
        if not parse_ok:
            val_warnings = ["json_parse_failed", *val_warnings]

        if _needs_retry(parse_ok, val_warnings):
            retry_reasons.append(
                ",".join(val_warnings[:3]) if val_warnings else "unknown_validation_failure"
            )
            continue
        break

    stance = str(canonical["stance"])
    confidence_f = float(canonical["confidence"])
    reasons = list(canonical["reasons"])
    stance_match = stance == reference_stance

    params_llm: dict[str, Any] = {
        "stance": stance,
        "confidence": round(confidence_f, 2),
        "reasons": reasons,
        "tool_events": tool_events,
        "debate_entries": len(transcript),
        "llm_json_parse_ok": parse_ok,
        "llm_validation_warnings": val_warnings,
        "llm_attempts": attempts,
        "llm_retry_reasons": retry_reasons[:5],
        "quant_desk_snapshot": quant_desk_bridge,
        "llm_reference_stance": reference_stance,
        "llm_reference_kind": reference_kind,
        "llm_vs_reference_stance_match": stance_match,
    }
    if tier1_deterministic is not None:
        params_llm["tier1_execution"] = tier1_deterministic

    proposed_signal = {
        "action": "PROPOSAL",
        "params": params_llm,
        "meta": {"source": "signal_arbitrator_llm", "model": model_name},
    }

    board = build_synthesis_board(state)
    intent = derive_trade_intent(state, proposed_signal)
    reasoning_logs = [
        _reasoning_entry(
            # Keep the canonical node id so topology + UI grouping work.
            node="signal_arbitrator",
            thought="LLM synthesized debate into proposed_signal (tool-calling enabled).",
            decision=proposed_signal,
            extra={
                "tool_events_count": len(tool_events),
                "llm": True,
                "synthesis_board": board,
                "llm_json_parse_ok": parse_ok,
                "llm_validation_warnings": val_warnings,
                "llm_reference_stance": reference_stance,
                "llm_vs_reference_stance_match": stance_match,
                "quant_desk_snapshot": quant_desk_bridge,
            },
        ),
        _reasoning_entry(
            node="execution_intent",
            thought="Execution intent derived from LLM thesis (same deterministic gate as rule path).",
            decision=intent,
            extra={"llm": True},
        ),
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
        "trade_intent": intent,
        "reasoning_logs": reasoning_logs,
    }


__all__ = ["sanitize_llm_arbitrator_output", "signal_arbitrator_llm"]
