"""Multi-window **anchored** backtests: fixed calendar ranges (not rolling “last N bars”).

Use this to answer “did the system trade, flatten, and how did it behave in named regimes?”
across history. Outcomes are **empirical** (sampled periods), not proof of future edge.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backtest.bars import fetch_ccxt_ohlcv_range, iso_utc_to_ms, nominal_interval_sec_for_timeframe
from backtest.loop import run_multi_step_backtest


@dataclass(frozen=True)
class HistoryWindowSpec:
    """One reproducible evaluation window (UTC calendar)."""

    id: str
    label: str
    since: str
    until: str
    timeframe: str = "1d"


# Default suite: six-month slices, daily bars — enough steps for entries/exits without huge LLM cost.
DEFAULT_DAILY_WINDOWS: tuple[HistoryWindowSpec, ...] = (
    HistoryWindowSpec(
        id="2022_h1",
        label="2022 H1 (macro risk-off)",
        since="2022-01-01",
        until="2022-06-30",
    ),
    HistoryWindowSpec(
        id="2023_h1",
        label="2023 H1",
        since="2023-01-01",
        until="2023-06-30",
    ),
    HistoryWindowSpec(
        id="2024_h1",
        label="2024 H1",
        since="2024-01-01",
        until="2024-06-30",
    ),
    HistoryWindowSpec(
        id="2024_h2",
        label="2024 H2",
        since="2024-07-01",
        until="2024-12-31",
    ),
)

# Coarser bars for LLM-capped runs (fewer graph steps).
LLM_MONTHLY_WINDOWS: tuple[HistoryWindowSpec, ...] = (
    HistoryWindowSpec(
        id="2022",
        label="2022 monthly",
        since="2022-01-01",
        until="2022-12-31",
        timeframe="1M",
    ),
    HistoryWindowSpec(
        id="2023",
        label="2023 monthly",
        since="2023-01-01",
        until="2023-12-31",
        timeframe="1M",
    ),
    HistoryWindowSpec(
        id="2024",
        label="2024 monthly",
        since="2024-01-01",
        until="2024-12-31",
        timeframe="1M",
    ),
)


def load_trades_file(path: Path) -> list[dict[str, Any]]:
    from backtest.trade_book import read_jsonl_dict_records

    return read_jsonl_dict_records(path)


def load_equity_file(path: Path) -> list[dict[str, Any]]:
    """Read equity curve from JSONL for quality checks."""
    from backtest.trade_book import read_jsonl_dict_records

    return read_jsonl_dict_records(path)


def summarize_execution_trades(trades: list[dict[str, Any]]) -> dict[str, Any]:
    buys = sum(1 for t in trades if str(t.get("side", "")).lower() == "buy")
    sells = sum(1 for t in trades if str(t.get("side", "")).lower() == "sell")
    return {
        "fills": len(trades),
        "buy_fills": buys,
        "sell_fills": sells,
        "opened_position": buys > 0,
        "reduced_or_flat": sells > 0,
        "round_trip_evidence": buys > 0 and sells > 0,
    }


def compute_regime_check(bars: list[list[float]]) -> dict[str, Any]:
    """Classify market regime from OHLCV bars (close prices).

    Uses ``_segment_regimes`` for multi-regime detection within a single window.
    """
    from backtest.validation import _segment_regimes, regime_coverage_check

    closes = [float(row[4]) for row in bars if len(row) > 4 and float(row[4]) > 0]
    if len(closes) < 10:
        return {"regimes_covered": ["insufficient_data"], "count": 0, "passed": False}
    return regime_coverage_check(_segment_regimes(closes))


def compute_quality_report(
    trades: list[dict[str, Any]],
    bars: list[list[float]],
    total_return_pct: float | None,
    profit_factor: float | None,
) -> dict[str, Any]:
    """Run all quality checks available at the window level."""
    from backtest.validation import generate_quality_report

    closes = [float(r[4]) for r in bars if len(r) > 4 and float(r[4]) > 0]
    tc = len(trades)
    tb = len(bars)

    return generate_quality_report(
        close_prices=closes,
        total_bars=tb,
        trade_count=tc,
        profit_factor=profit_factor,
        trades=trades,
    ).to_dict()


def _infer_interval_sec(bars: list[list[float]], timeframe: str) -> int:
    if len(bars) >= 2:
        dt_ms = float(bars[1][0] - bars[0][0])
        return max(60, int(dt_ms / 1000.0))
    return nominal_interval_sec_for_timeframe(timeframe)


def run_window(
    spec: HistoryWindowSpec,
    *,
    ticker: str,
    exchange: str,
    initial_cash: float,
    runs_dir: Path,
    eval_tag: str,
    use_llm: bool,
    llm_max_steps: int,
    export_bundle: bool = False,
    deploy_profile_weights: dict[str, float] | None = None,
    deploy_profile_id: str | None = None,
    deploy_arbitrator_mode: str | None = None,
    take_profit_pct: float = 0.0,
    stop_loss_pct: float = 0.0,
    max_hold_bars: int = 0,
    forward_validate: bool = False,
    forward_oos_bars: int = 30,
    deploy_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    since_ms = iso_utc_to_ms(spec.since)
    last_day_ms = iso_utc_to_ms(spec.until)
    # Inclusive through end of ``until`` calendar day (UTC).
    until_ms = last_day_ms + 86_400_000 - 1

    bars = fetch_ccxt_ohlcv_range(
        ticker,
        timeframe=spec.timeframe,
        since_ms=since_ms,
        until_ms=until_ms,
        exchange_id=exchange,
    )
    max_steps: int | None = None
    if use_llm:
        max_steps = max(2, int(llm_max_steps))
        if len(bars) > max_steps:
            bars = bars[-max_steps:]

    interval_sec = _infer_interval_sec(bars, spec.timeframe)
    interval_sec = max(interval_sec, nominal_interval_sec_for_timeframe(spec.timeframe))

    forward_report: dict[str, Any] | None = None
    if forward_validate and len(bars) > forward_oos_bars * 2:
        n_bars = len(bars)
        split_point = n_bars - min(forward_oos_bars, n_bars // 2)
        is_bars = bars[:split_point]
        oos_bars_list = bars[split_point:]

        is_run_id = f"{eval_tag}_{spec.id}_is"
        is_res = run_multi_step_backtest(
            ticker=ticker,
            bars=is_bars,
            initial_cash=initial_cash,
            interval_sec=interval_sec,
            run_id=is_run_id,
            runs_dir=runs_dir,
            export_bundle=False,
            deploy_profile_weights=deploy_profile_weights,
            deploy_profile_id=deploy_profile_id,
            deploy_arbitrator_mode=deploy_arbitrator_mode,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            max_hold_bars=max_hold_bars,
            deploy_config=deploy_config,
        )

        oos_run_id = f"{eval_tag}_{spec.id}_oos"
        oos_res = run_multi_step_backtest(
            ticker=ticker,
            bars=oos_bars_list,
            initial_cash=initial_cash,
            interval_sec=interval_sec,
            run_id=oos_run_id,
            runs_dir=runs_dir,
            export_bundle=False,
            deploy_profile_weights=deploy_profile_weights,
            deploy_profile_id=deploy_profile_id,
            deploy_arbitrator_mode=deploy_arbitrator_mode,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            max_hold_bars=max_hold_bars,
            deploy_config=deploy_config,
        )

        is_pf = (is_res.metrics or {}).get("profit_factor") or 0.0
        oos_pf = (oos_res.metrics or {}).get("profit_factor") or 0.0
        is_ret = ((float(is_res.final_equity or initial_cash) / initial_cash) - 1.0) * 100.0
        oos_ret = ((float(oos_res.final_equity or initial_cash) / initial_cash) - 1.0) * 100.0

        # OOS passes if profit factor >= 1.0 (positive edge) or within 50% of IS
        threshold = max(1.0, is_pf * 0.5) if is_pf > 0 else 1.0
        passed = oos_pf >= threshold
        notes = (
            f"IS PF {is_pf:.2f} ({is_ret:+.2f}%) → OOS PF {oos_pf:.2f} ({oos_ret:+.2f}%), "
            f"threshold={threshold:.2f}"
        )

        forward_report = {
            "in_sample_bars": len(is_bars),
            "out_of_sample_bars": len(oos_bars_list),
            "in_sample_profit_factor": round(is_pf, 4),
            "out_of_sample_profit_factor": round(oos_pf, 4),
            "in_sample_return_pct": round(is_ret, 4),
            "out_of_sample_return_pct": round(oos_ret, 4),
            "passed": bool(passed),
            "notes": notes,
        }

    run_id = f"{eval_tag}_{spec.id}"
    res = run_multi_step_backtest(
        ticker=ticker,
        bars=bars,
        initial_cash=initial_cash,
        interval_sec=interval_sec,
        run_id=run_id,
        runs_dir=runs_dir,
        export_bundle=export_bundle,
        deploy_profile_weights=deploy_profile_weights,
        deploy_profile_id=deploy_profile_id,
        deploy_arbitrator_mode=deploy_arbitrator_mode,
        take_profit_pct=take_profit_pct,
        stop_loss_pct=stop_loss_pct,
        max_hold_bars=max_hold_bars,
        deploy_config=deploy_config,
    )
    trades = load_trades_file(res.trades_path)
    ex = summarize_execution_trades(trades)
    initial = float(initial_cash)
    final = float(res.final_equity) if res.final_equity is not None else initial
    ret_pct = ((final - initial) / initial * 100.0) if initial else 0.0
    m = res.metrics or {}
    bench = dict(res.benchmark) if res.benchmark is not None else {}

    pf = m.get("profit_factor") or m.get("profit_factor_pct") or None
    quality = compute_quality_report(
        trades=trades,
        bars=bars,
        total_return_pct=ret_pct,
        profit_factor=float(pf) if pf is not None else None,
    )

    return {
        "window_id": spec.id,
        "label": spec.label,
        "since": spec.since,
        "until": spec.until,
        "timeframe": spec.timeframe,
        "bars_used": len(bars),
        "run_id": res.run_id,
        "steps": res.steps,
        "initial_cash_usd": initial,
        "final_equity_usd": round(final, 2),
        "total_return_pct": round(ret_pct, 4),
        "benchmark": bench,
        "metrics": m,
        "execution": ex,
        "quality": quality,
        "paths": {
            "summary": str(res.summary_path),
            "trades": str(res.trades_path),
            "equity": str(res.equity_path),
            "iterations": str(res.iterations_path) if res.iterations_path else None,
        },
        "forward_validation": forward_report,
    }


def build_aggregate(windows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(windows)
    prof = sum(1 for w in windows if float(w.get("total_return_pct") or 0) > 0)
    rets = [float(w.get("total_return_pct") or 0) for w in windows]
    mean_ret = sum(rets) / n if n else 0.0
    trips = sum(1 for w in windows if (w.get("execution") or {}).get("round_trip_evidence"))
    with_sell = sum(1 for w in windows if (w.get("execution") or {}).get("reduced_or_flat"))
    with_buy = sum(1 for w in windows if (w.get("execution") or {}).get("opened_position"))

    bh_eq: list[float] = []
    excess: list[float] = []
    for w in windows:
        b = w.get("benchmark") or {}
        if isinstance(b, dict):
            raw_bh = b.get("benchmark_buy_hold_equity_return_pct")
            raw_ex = b.get("excess_return_vs_buy_hold_equity_pct")
            if raw_bh is not None:
                try:
                    bh_eq.append(float(raw_bh))
                except (TypeError, ValueError):
                    pass
            if raw_ex is not None:
                try:
                    excess.append(float(raw_ex))
                except (TypeError, ValueError):
                    pass
    beat_bh = sum(1 for e in excess if e > 0.0)

    all_pass = all(w.get("quality", {}).get("overall_passed", True) for w in windows)
    sample_warnings = [
        w.get("quality", {}).get("sample_size", {}).get("warning", "")
        for w in windows
        if w.get("quality", {}).get("sample_size", {}).get("warning")
    ]
    pl_warnings = [
        w.get("quality", {}).get("profit_loss_ratio", {}).get("warning", "")
        for w in windows
        if w.get("quality", {}).get("profit_loss_ratio", {}).get("warning")
    ]
    exit_warnings = [
        w.get("quality", {}).get("exit_reasons", {}).get("warning", "")
        for w in windows
        if isinstance(w.get("quality"), dict)
        and isinstance(w.get("quality", {}).get("exit_reasons"), dict)
        and w["quality"]["exit_reasons"].get("warning")
    ]

    agg: dict[str, Any] = {
        "window_count": n,
        "profitable_windows": prof,
        "pct_windows_profitable": round(prof / n, 4) if n else 0.0,
        "mean_total_return_pct": round(mean_ret, 4),
        "windows_with_buy": with_buy,
        "windows_with_sell": with_sell,
        "windows_with_round_trip": trips,
        "windows_beat_buy_hold_equity": beat_bh,
        "pct_windows_beat_buy_hold_equity": round(beat_bh / n, 4) if n else 0.0,
        "quality": {
            "all_windows_passed": all_pass,
            "sample_size_warnings": sample_warnings[:3],  # cap output
            "profit_loss_warnings": pl_warnings[:3],
            "exit_reason_warnings": exit_warnings[:3],
        },
    }
    if bh_eq:
        agg["mean_benchmark_buy_hold_equity_return_pct"] = round(sum(bh_eq) / len(bh_eq), 4)
    if excess:
        agg["mean_excess_return_vs_buy_hold_equity_pct"] = round(sum(excess) / len(excess), 4)
    return agg


def run_suite(
    windows: tuple[HistoryWindowSpec, ...],
    *,
    ticker: str,
    exchange: str,
    initial_cash: float,
    runs_dir: Path,
    use_llm: bool,
    llm_max_steps: int,
    deploy_profile_weights: dict[str, float] | None = None,
    deploy_profile_id: str | None = None,
    deploy_arbitrator_mode: str | None = None,
    take_profit_pct: float = 0.0,
    stop_loss_pct: float = 0.0,
    max_hold_bars: int = 0,
    forward_validate: bool = False,
    forward_oos_bars: int = 30,
    deploy_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    eval_tag = f"eval_{int(time.time())}"
    out_dir = runs_dir / "evaluations" / eval_tag
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for spec in windows:
        rows.append(
            run_window(
                spec,
                ticker=ticker,
                exchange=exchange,
                initial_cash=initial_cash,
                runs_dir=runs_dir,
                eval_tag=eval_tag,
                use_llm=use_llm,
                llm_max_steps=llm_max_steps,
                export_bundle=False,
                deploy_profile_weights=deploy_profile_weights,
                deploy_profile_id=deploy_profile_id,
                deploy_arbitrator_mode=deploy_arbitrator_mode,
                take_profit_pct=take_profit_pct,
                stop_loss_pct=stop_loss_pct,
                max_hold_bars=max_hold_bars,
                forward_validate=forward_validate,
                forward_oos_bars=forward_oos_bars,
                deploy_config=deploy_config,
            )
        )
        print(
            f"  [{spec.id}] {len(rows[-1].get('bars', []))} bars, "
            f"{rows[-1].get('execution', {}).get('fills', 0)} trades, "
            f"return {rows[-1].get('total_return_pct', 'n/a')}%",
            file=sys.stderr,
        )

    agg = build_aggregate(rows)
    report = {
        "eval_id": eval_tag,
        "methodology": (
            "Anchored UTC calendar windows; OHLCV fetched by time range (reproducible for a given "
            "exchange snapshot). Reports realized fills (buy/sell) and summary metrics per window. "
            "Each window reports strategy return vs buy-and-hold on the same bars "
            "(asset % and fee-realistic round-trip equity). Beating that baseline is the honest "
            "active-management bar; positive mean return alone is not."
        ),
        "ticker": ticker,
        "exchange": exchange,
        "llm": use_llm,
        "llm_max_steps_cap": llm_max_steps if use_llm else None,
        "windows": rows,
        "aggregate": agg,
    }
    report_path = out_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report


def report_to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Historical evaluation report",
        "",
        report.get("methodology", ""),
        "",
        f"- **Eval id:** `{report.get('eval_id')}`",
        f"- **Ticker:** {report.get('ticker')}",
        f"- **Exchange:** {report.get('exchange')}",
        f"- **LLM:** {report.get('llm')}",
        "",
        "## Quality assessment",
        "",
    ]
    a = report.get("aggregate") or {}
    qual = a.get("quality") or {}
    lines.append(f"- **All windows passed:** {'✅' if qual.get('all_windows_passed') else '❌'}")
    sw = qual.get("sample_size_warnings") or []
    if sw:
        lines.append(f"- Sample size warnings: {len(sw)}")
        for ww in sw[:2]:
            lines.append(f"  - {ww}")
    pw = qual.get("profit_loss_warnings") or []
    if pw:
        lines.append(f"- Profit/loss warnings: {len(pw)}")
        for ww in pw[:2]:
            lines.append(f"  - {ww}")
    ew = qual.get("exit_reason_warnings") or []
    if ew:
        lines.append(f"- Exit reason warnings: {len(ew)}")
        for ww in ew[:2]:
            lines.append(f"  - {ww}")

    lines.extend(
        [
            "",
            "## Per window",
            "",
            "| Window | Bars | Strat % | BH eq % | Excess % | Buys | Sells | RT | Sharpe | Max DD | Quality | Fwd Val |",
            "|--------|-----:|--------:|--------:|---------:|-----:|------:|:--:|-------:|-------:|:-------:|:--------:|",
        ]
    )
    for w in report.get("windows") or []:
        ex = w.get("execution") or {}
        m = w.get("metrics") or {}
        b = w.get("benchmark") or {}
        bh_eq = b.get("benchmark_buy_hold_equity_return_pct", "")
        xs = b.get("excess_return_vs_buy_hold_equity_pct", "")
        q = w.get("quality", {}) or {}
        fwd = w.get("forward_validation") or {}
        fwd_ok = "✅" if fwd.get("passed") else ("N/A" if not fwd else "❌")
        q_ok = "✅" if q.get("overall_passed") else "❌"
        lines.append(
            "| {label} | {bars} | {ret} | {bh} | {xs} | {buys} | {sells} | {rt} | {sharpe:.3f} | {mdd:.4f} | {q} | {fwd} |".format(
                label=str(w.get("label", w.get("window_id", "")))[:28],
                bars=int(w.get("bars_used") or 0),
                ret=w.get("total_return_pct"),
                bh=bh_eq,
                xs=xs,
                buys=ex.get("buy_fills", 0),
                sells=ex.get("sell_fills", 0),
                rt="yes" if ex.get("round_trip_evidence") else "no",
                sharpe=float(m.get("sharpe") or 0),
                mdd=float(m.get("max_drawdown") or 0),
                q=q_ok,
                fwd=fwd_ok,
            )
        )
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- Windows: **{a.get('window_count')}**",
            f"- Profitable windows: **{a.get('profitable_windows')}** "
            f"({float(a.get('pct_windows_profitable') or 0) * 100:.1f}%)",
            f"- Mean return %: **{a.get('mean_total_return_pct')}**",
            f"- Mean buy-hold (equity, same fees) %: **{a.get('mean_benchmark_buy_hold_equity_return_pct', 'n/a')}**",
            f"- Mean excess vs buy-hold equity %: **{a.get('mean_excess_return_vs_buy_hold_equity_pct', 'n/a')}**",
            f"- Windows beating buy-hold equity: **{a.get('windows_beat_buy_hold_equity')}** "
            f"({float(a.get('pct_windows_beat_buy_hold_equity') or 0) * 100:.1f}%)",
            f"- Windows with ≥1 buy: **{a.get('windows_with_buy')}**",
            f"- Windows with ≥1 sell: **{a.get('windows_with_sell')}**",
            f"- Windows with buy+sell: **{a.get('windows_with_round_trip')}**",
            f"- All windows passing quality: {'✅' if qual.get('all_windows_passed') else '❌'}",
            "",
        ]
    )

    lines.append("## Quality details by window")
    for w in report.get("windows") or []:
        wid = str(w.get("label", w.get("window_id", "")))[:28]
        q = w.get("quality", {}) or {}
        lines.append("")
        lines.append(f"### {wid}")
        ss = q.get("sample_size", {}) or {}
        lines.append(
            f"- Sample: {ss.get('total_bars', '?')} bars, {ss.get('trade_count', '?')} trades → {'✅' if ss.get('passed') else '❌'}"
        )
        pl = q.get("profit_loss_ratio", {}) or {}
        pf_v = pl.get("profit_factor")
        if pf_v is not None:
            lines.append(
                f"- Profit factor: {pf_v:.2f} (threshold 1.3) → {'✅' if pl.get('passed') else '❌'}"
            )
        er = q.get("exit_reasons", {}) or {}
        if er.get("pct_distribution"):
            pct_strs = [f"{k}={v:.0f}%" for k, v in er["pct_distribution"].items()]
            lines.append(f"- Exit reasons: {', '.join(pct_strs)}")
        rc = q.get("regime_coverage", {}) or {}
        if rc.get("regimes_covered"):
            lines.append(f"- Market regimes: {', '.join(rc['regimes_covered'])}")
        fwd = w.get("forward_validation") or {}
        if fwd:
            is_note = fwd.get("notes", "")
            f_passed = "✅" if fwd.get("passed") else "❌"
            lines.append(f"- Forward validation: {f_passed} ({is_note})")
        if not ss.get("passed") or not pl.get("passed") or not er.get("passed", True):
            for lw in [ss.get("warning"), pl.get("warning"), er.get("warning")]:
                if lw:
                    lines.append(f"  - ⚠️ {lw}")

    return "\n".join(lines)


__all__ = [
    "DEFAULT_DAILY_WINDOWS",
    "LLM_MONTHLY_WINDOWS",
    "HistoryWindowSpec",
    "build_aggregate",
    "load_trades_file",
    "report_to_markdown",
    "run_suite",
    "run_window",
    "summarize_execution_trades",
]
