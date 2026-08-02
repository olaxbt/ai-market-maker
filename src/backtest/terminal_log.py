"""Human-readable backtest terminal output (decisions, CoT, summary).

Replaces raw HTTP/LLM client noise with a TradingAgents-style decision transcript.
Enabled by default when ``MODE=backtest``; disable with ``AIMM_BACKTEST_TERMINAL_LOG=0``.
"""

from __future__ import annotations

import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, TextIO

_AGENT_LABELS: dict[str, str] = {
    "1.1": "Macro Sentinel",
    "1.2": "News & Narrative",
    "2.1": "Pattern Recognition",
    "2.3": "Technical TA",
    "2.2": "Statistical Alpha",
    "3.1": "Retail Hype",
    "3.2": "Pro Bias",
    "4.1": "Whale Behavior",
    "4.2": "Liquidity / Flow",
}

_CONFIGURED = False
_API_WARNED = False
_ARB_BOILERPLATE = re.compile(r"^Agent \[")


def backtest_terminal_log_enabled() -> bool:
    if (os.environ.get("MODE") or "").strip().lower() != "backtest":
        return False
    flag = (os.environ.get("AIMM_BACKTEST_TERMINAL_LOG") or "1").strip().lower()
    return flag not in ("0", "false", "no", "off")


def _terminal_all_symbols() -> bool:
    return (os.environ.get("AIMM_BACKTEST_TERMINAL_ALL_SYMBOLS") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


class _BacktestTerminalNoiseFilter(logging.Filter):
    """Drop repetitive LLM HTTP errors — surfaced once via ``note_llm_api_error``."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "LLM request failed" in msg or "agent_llm: LLM call failed" in msg:
            return False
        if "LLM portfolio_proposal failed" in msg or "LLM portfolio_execute failed" in msg:
            return False
        if "agent_llm mode: running LLM inference" in msg:
            return False
        if "HTTP Request:" in msg:
            return False
        return True


def quiet_backtest_library_loggers() -> None:
    """Mute SDK/HTTP loggers in backtest mode (independent of desk CoT)."""
    if (os.environ.get("MODE") or "").strip().lower() != "backtest":
        return
    for name in (
        "httpx",
        "httpcore",
        "openai",
        "openai._base_client",
        "urllib3",
        "llm.agent_llm_client",
        "llm.openai_client",
        "workflow.weighted_arbitrator",
        "main",
        "llm.portfolio_llm",
        "agents.portfolio_management",
    ):
        lg = logging.getLogger(name)
        lg.setLevel(logging.WARNING)
        if not any(isinstance(f, _BacktestTerminalNoiseFilter) for f in lg.filters):
            lg.addFilter(_BacktestTerminalNoiseFilter())


def configure_backtest_terminal_logging() -> None:
    """Mute SDK/HTTP loggers; desk CoT uses stderr prints."""
    global _CONFIGURED
    quiet_backtest_library_loggers()
    if _CONFIGURED or not backtest_terminal_log_enabled():
        return
    _CONFIGURED = True
    for name in (
        "httpx",
        "httpcore",
        "openai",
        "openai._base_client",
        "urllib3",
        "llm.agent_llm_client",
        "llm.openai_client",
        "workflow.weighted_arbitrator",
        "main",
        "llm.portfolio_llm",
        "agents.portfolio_management",
    ):
        logging.getLogger(name).setLevel(logging.CRITICAL)


def note_llm_api_error(message: str) -> None:
    """Print a single provider-balance warning instead of per-call stack traces."""
    global _API_WARNED
    if not backtest_terminal_log_enabled() or _API_WARNED:
        return
    _API_WARNED = True
    print(
        f"\n⚠ LLM provider error (subsequent calls may show neutral/error desks): "
        f"{_clip(message, 120)}\n"
        f"   Top up API balance or rely on `.cache/decisions/` for warm historical bars.\n",
        file=sys.stderr,
        flush=True,
    )


def _clip(text: str, limit: int = 220) -> str:
    t = " ".join((text or "").split())
    if len(t) <= limit:
        return t
    return t[: limit - 1] + "…"


def _fmt_composite(value: Any) -> str:
    """Render composite on a 0–100 scale (matches decision gates)."""
    if value is None:
        return "—"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "—"
    # Agent contracts sometimes use 0–100; arbitration uses 0–1.
    if 0.0 <= v <= 1.5:
        v *= 100.0
    return f"{v:.0f}"


def _bar_date(ts_ms: int | float | None) -> str:
    if ts_ms is None:
        return "—"
    try:
        return datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
    except (OSError, OverflowError, ValueError):
        return "—"


def _stance_icon(stance: str) -> str:
    s = (stance or "").lower()
    if "bull" in s:
        return "▲"
    if "bear" in s:
        return "▼"
    return "·"


def _action_badge(action: str) -> str:
    a = (action or "HOLD").upper()
    if a == "BUY":
        return "BUY "
    if a == "SELL":
        return "SELL"
    return "HOLD"


def _agent_priority(source: str | None) -> int:
    if source == "agent_llm":
        return 3
    if source == "error":
        return 2
    if source:
        return 1
    return 0


def _extract_arbitration(wf_output: dict[str, Any]) -> dict[str, Any] | None:
    arb = wf_output.get("arbitration_result")
    if isinstance(arb, dict) and arb:
        return arb
    for log in wf_output.get("reasoning_logs") or []:
        if not isinstance(log, dict) or log.get("node") != "signal_arbitrator":
            continue
        dec = log.get("decision")
        if isinstance(dec, dict) and dec.get("composite_score") is not None:
            return {
                "composite": dec.get("composite_score"),
                "confidence": dec.get("confidence"),
                "stance": dec.get("stance"),
                "conviction_level": dec.get("conviction_level"),
            }
    return None


def _extract_agent_rows(
    wf_output: dict[str, Any],
    *,
    active_agent_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Desk rows for terminal CoT — active LLM desks only, deduped."""
    active = [str(a) for a in (active_agent_ids or []) if str(a).strip()]
    if not active:
        pw = wf_output.get("profile_weights")
        if isinstance(pw, dict) and pw:
            active = [str(a) for a, w in pw.items() if float(w or 0) > 0]
    if not active:
        active = ["2.3", "2.1", "1.1"]

    by_id: dict[str, dict[str, Any]] = {}

    def _merge(aid: str, row: dict[str, Any]) -> None:
        prev = by_id.get(aid)
        if prev is None or _agent_priority(row.get("source")) > _agent_priority(prev.get("source")):
            by_id[aid] = row

    contracts = wf_output.get("tier0_contracts")
    if isinstance(contracts, list):
        for c in contracts:
            if not isinstance(c, dict):
                continue
            aid = str(c.get("agent_id") or c.get("agent") or "")
            if not aid or aid not in active:
                continue
            src = c.get("source")
            if c.get("status") == "skipped" and src not in ("agent_llm", "error"):
                continue
            reasoning = c.get("reasoning") if isinstance(c.get("reasoning"), str) else ""
            if reasoning and _ARB_BOILERPLATE.match(reasoning.strip()):
                reasoning = ""
            llm_err = c.get("llm_error")
            if src == "error" and llm_err:
                reasoning = f"LLM unavailable: {_clip(str(llm_err), 160)}"
            _merge(
                aid,
                {
                    "agent_id": aid,
                    "label": str(c.get("label") or _AGENT_LABELS.get(aid, aid)),
                    "composite": c.get("composite"),
                    "confidence": c.get("confidence"),
                    "stance": c.get("stance", "neutral"),
                    "source": src,
                    "cached": bool(c.get("cached")),
                    "reasoning": reasoning.strip() if reasoning else "",
                },
            )

    for log in wf_output.get("reasoning_logs") or []:
        if not isinstance(log, dict):
            continue
        extra = log.get("extra") if isinstance(log.get("extra"), dict) else {}
        aid = str(extra.get("agent_id") or "")
        if not aid or aid not in active:
            continue
        dec = log.get("decision") if isinstance(log.get("decision"), dict) else {}
        thought = str(log.get("thought_process") or log.get("reasoning_chain") or "")
        if _ARB_BOILERPLATE.match(thought.strip()):
            thought = ""
        existing = by_id.get(aid)
        if existing is not None:
            # Prefer arbitration scores when the LLM contract omitted composite/stance.
            for key in ("composite", "confidence", "stance"):
                if existing.get(key) is None and dec.get(key) is not None:
                    existing[key] = dec.get(key)
            if not existing.get("reasoning") and thought:
                existing["reasoning"] = thought
            continue
        _merge(
            aid,
            {
                "agent_id": aid,
                "label": str(dec.get("label") or _AGENT_LABELS.get(aid, aid)),
                "composite": dec.get("composite"),
                "confidence": dec.get("confidence"),
                "stance": dec.get("stance", "neutral"),
                "source": "arbitration",
                "cached": False,
                "reasoning": thought,
            },
        )

    # Fill gaps from proposed_signal.params.agent_signals.
    params = (wf_output.get("proposed_signal") or {}).get("params")
    if isinstance(params, dict):
        for s in params.get("agent_signals") or []:
            if not isinstance(s, dict):
                continue
            aid = str(s.get("agent_id") or "")
            if not aid or aid not in active:
                continue
            existing = by_id.get(aid)
            if existing is None:
                continue
            for key in ("composite", "confidence", "stance"):
                if existing.get(key) is None and s.get(key) is not None:
                    existing[key] = s.get(key)

    order = {aid: i for i, aid in enumerate(active)}
    return sorted(by_id.values(), key=lambda r: order.get(str(r["agent_id"]), 99))


def _should_print_bar(*, symbol: str, primary_symbol: str, action: str, confidence: float) -> bool:
    if _terminal_all_symbols() or symbol == primary_symbol:
        pass
    else:
        return False
    if action in ("BUY", "SELL"):
        return True
    if confidence >= 0.12:
        return True
    return False


def print_run_header(
    *,
    run_id: str,
    symbols: list[str],
    total_bars: int,
    profile_id: str = "",
    profile_weights: dict[str, float] | None = None,
    ta_warmup_bars: int = 0,
    eval_bars: int | None = None,
    stream: TextIO | None = None,
) -> None:
    if not backtest_terminal_log_enabled():
        return
    out = stream or sys.stderr
    sym_s = ", ".join(symbols[:6])
    if len(symbols) > 6:
        sym_s += f" (+{len(symbols) - 6})"
    prof = f" │ preset {profile_id}" if profile_id else ""
    desks = ""
    if profile_weights:
        parts = [
            f"{k}×{float(v):.2f}" for k, v in sorted(profile_weights.items(), key=lambda x: -x[1])
        ]
        desks = f"\n desks:   {', '.join(parts)} (LLM CoT)"
    ev = eval_bars if eval_bars is not None else max(0, total_bars - ta_warmup_bars)
    warmup_line = (
        f"\n warmup:  {ta_warmup_bars} bars (TA context only — no LLM, no trades)"
        if ta_warmup_bars > 0
        else ""
    )
    bars_line = f" bars:    {total_bars} loaded · {ev} eval"
    if ta_warmup_bars > 0:
        bars_line += f" · {ta_warmup_bars} warmup"
    sym_mode = (
        "all symbols" if _terminal_all_symbols() else f"primary {symbols[0] if symbols else '—'}"
    )
    print(
        f"\n{'█' * 72}\n"
        f" AIMM AGENTIC BACKTEST  run_id={run_id}{prof}\n"
        f" symbols: {sym_s}\n"
        f"{bars_line}"
        f"{warmup_line}"
        f"{desks}\n"
        f" transcript: {sym_mode} │ BUY/SELL + high-confidence bars\n"
        f"{'█' * 72}",
        file=out,
        flush=True,
    )


def print_bar_decision(
    *,
    bar_index: int,
    total_bars: int,
    symbol: str,
    primary_symbol: str = "",
    close: float | None,
    ts_ms: int | float | None,
    wf_output: dict[str, Any],
    action: str,
    confidence: float,
    equity: float | None = None,
    trade_count: int | None = None,
    invoke_cache_hit: bool = False,
    active_agent_ids: list[str] | None = None,
    stream: TextIO | None = None,
) -> None:
    if not backtest_terminal_log_enabled():
        return
    primary = primary_symbol or symbol
    if not _should_print_bar(
        symbol=symbol, primary_symbol=primary, action=action, confidence=confidence
    ):
        return

    out = stream or sys.stderr
    date_s = _bar_date(ts_ms)
    close_s = f"${close:,.2f}" if close is not None and close > 0 else "—"
    header = (
        f"\n{'═' * 72}\n"
        f" Bar {bar_index:>4}/{total_bars:<4} │ {symbol:<12} │ {date_s} │ close {close_s}"
    )
    if invoke_cache_hit:
        header += " │ cache"
    print(header, file=out)

    arb = _extract_arbitration(wf_output)
    if isinstance(arb, dict):
        conf = float(arb.get("confidence") or 0)
        print(
            f" Arbitration: composite {_fmt_composite(arb.get('composite'))}/100 │ conf {conf:.2f} "
            f"│ {_stance_icon(str(arb.get('stance', '')))} {arb.get('stance', 'neutral')}",
            file=out,
        )

    agents = _extract_agent_rows(wf_output, active_agent_ids=active_agent_ids)
    if agents:
        print(f"{'─' * 72}", file=out)
        print(" Desk deliberation (chain-of-thought):", file=out)
        for row in agents:
            src = row.get("source") or "tier0"
            tags: list[str] = []
            if row.get("cached"):
                tags.append("cached")
            if src == "error":
                tags.append("error")
            tag_s = f" ({', '.join(tags)})" if tags else ""
            conf_a = row.get("confidence")
            conf_s = f"{float(conf_a):.2f}" if conf_a is not None else "—"
            print(
                f"  [{row['agent_id']}] {row['label']:<22} │ "
                f"comp {_fmt_composite(row.get('composite')):>3}/100 "
                f"│ conf {conf_s} "
                f"│ {_stance_icon(str(row.get('stance', '')))} {str(row.get('stance', 'neutral')):<8}"
                f"{tag_s}",
                file=out,
            )
            reason = row.get("reasoning") or ""
            if reason:
                print(f"      {_clip(reason, 320)}", file=out)
            elif src == "error":
                print("      (no CoT — provider error; check API balance)", file=out)

        # Note when desks are neutral but gates still fire a directional action.
        stances = [str(r.get("stance") or "neutral").lower() for r in agents]
        bull = sum(1 for s in stances if "bull" in s)
        bear = sum(1 for s in stances if "bear" in s)
        act = (action or "HOLD").upper()
        if act == "BUY" and bear > bull:
            print("  ⚠ net desk lean bearish — BUY from weighted gates / TA-led override", file=out)
        elif act == "SELL" and bull > bear:
            print(
                "  ⚠ net desk lean bullish — SELL from weighted gates / TA-led override", file=out
            )
        elif act in ("BUY", "SELL") and bull == 0 and bear == 0:
            print("  ⓘ desks neutral — directional from composite gates / TA-led", file=out)

    intent = wf_output.get("trade_intent")
    if isinstance(intent, dict) and intent.get("rationale"):
        print(f" Intent rationale: {_clip(str(intent.get('rationale')), 280)}", file=out)

    eq_s = f"${equity:,.2f}" if equity is not None else "—"
    tc_s = str(trade_count) if trade_count is not None else "—"
    print(
        f"{'─' * 72}\n"
        f" ▶ Decision: {_action_badge(action)}  conf {confidence:.2f} "
        f"│ equity {eq_s}  trades {tc_s}\n"
        f"{'═' * 72}",
        file=out,
        flush=True,
    )


def print_run_summary(
    *,
    run_id: str,
    metrics: dict[str, Any],
    benchmark: dict[str, Any] | None = None,
    trade_count: int = 0,
    steps: int = 0,
    paths: dict[str, str] | None = None,
    stream: TextIO | None = None,
) -> None:
    if not backtest_terminal_log_enabled():
        return
    out = stream or sys.stderr
    m = metrics or {}
    bench = benchmark or {}
    ret = float(m.get("total_return_pct") or 0)
    sharpe = float(m.get("sharpe") or 0)
    max_dd = float(m.get("max_drawdown_pct") or 0)
    pf = m.get("profit_factor")
    pf_s = f"{float(pf):.2f}" if pf is not None else "—"
    bench_ret = bench.get("benchmark_buy_hold_equity_return_pct") or bench.get(
        "buy_hold_return_pct"
    )
    excess = bench.get("excess_return_vs_buy_hold_equity_pct") or bench.get("excess_return_pct")
    bench_line = ""
    if bench_ret is not None:
        bench_line = f"\n │ vs buy-and-hold: {float(bench_ret):+.2f}%"
        if excess is not None:
            bench_line += f"  (excess {float(excess):+.2f}%)"

    print(
        f"\n{'█' * 72}\n"
        f" BACKTEST COMPLETE  run_id={run_id}\n"
        f"{'─' * 72}\n"
        f" │ bars simulated: {steps}\n"
        f" │ trades:         {trade_count}\n"
        f" │ return:         {ret:+.2f}%\n"
        f" │ sharpe:         {sharpe:.2f}\n"
        f" │ max drawdown:   {max_dd:.2f}%\n"
        f" │ profit factor:  {pf_s}"
        f"{bench_line}\n"
        f"{'─' * 72}",
        file=out,
    )
    if paths:
        summary = paths.get("summary") or paths.get("summary_path")
        report = paths.get("report") or paths.get("report_path")
        if summary:
            print(f" │ summary:  {summary}", file=out)
        if report:
            print(f" │ report:   {report}", file=out)
    print(f"{'█' * 72}\n", file=out, flush=True)


__all__ = [
    "backtest_terminal_log_enabled",
    "quiet_backtest_library_loggers",
    "configure_backtest_terminal_logging",
    "note_llm_api_error",
    "print_run_header",
    "print_bar_decision",
    "print_run_summary",
]
