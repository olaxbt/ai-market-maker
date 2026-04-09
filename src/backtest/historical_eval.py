"""Multi-window **anchored** backtests: fixed calendar ranges (not rolling “last N bars”).

Use this to answer “did the system trade, flatten, and how did it behave in named regimes?”
across history. Outcomes are **empirical** (sampled periods), not proof of future edge.
"""

from __future__ import annotations

import json
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

    run_id = f"{eval_tag}_{spec.id}"
    res = run_multi_step_backtest(
        ticker=ticker,
        bars=bars,
        initial_cash=initial_cash,
        interval_sec=interval_sec,
        run_id=run_id,
        runs_dir=runs_dir,
        export_bundle=export_bundle,
    )
    trades = load_trades_file(res.trades_path)
    ex = summarize_execution_trades(trades)
    initial = float(initial_cash)
    final = float(res.final_equity) if res.final_equity is not None else initial
    ret_pct = ((final - initial) / initial * 100.0) if initial else 0.0
    m = res.metrics or {}
    bench = dict(res.benchmark) if res.benchmark is not None else {}
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
        "paths": {
            "summary": str(res.summary_path),
            "trades": str(res.trades_path),
            "equity": str(res.equity_path),
            "iterations": str(res.iterations_path) if res.iterations_path else None,
        },
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
            )
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
        "## Per window",
        "",
        "| Window | Bars | Strat % | BH eq % | Excess % | Buys | Sells | RT | Sharpe | Max DD |",
        "|--------|-----:|--------:|--------:|---------:|-----:|------:|:--:|-------:|-------:|",
    ]
    for w in report.get("windows") or []:
        ex = w.get("execution") or {}
        m = w.get("metrics") or {}
        b = w.get("benchmark") or {}
        bh_eq = b.get("benchmark_buy_hold_equity_return_pct", "")
        xs = b.get("excess_return_vs_buy_hold_equity_pct", "")
        lines.append(
            "| {label} | {bars} | {ret} | {bh} | {xs} | {buys} | {sells} | {rt} | {sharpe:.3f} | {mdd:.4f} |".format(
                label=str(w.get("label", w.get("window_id", "")))[:32],
                bars=int(w.get("bars_used") or 0),
                ret=w.get("total_return_pct"),
                bh=bh_eq,
                xs=xs,
                buys=ex.get("buy_fills", 0),
                sells=ex.get("sell_fills", 0),
                rt="yes" if ex.get("round_trip_evidence") else "no",
                sharpe=float(m.get("sharpe") or 0),
                mdd=float(m.get("max_drawdown") or 0),
            )
        )
    a = report.get("aggregate") or {}
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
            "",
        ]
    )
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
