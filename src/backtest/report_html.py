"""Self-contained HTML backtest report from a persisted run directory."""

from __future__ import annotations

import csv
import html
import json
import math
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backtest.iteration_decision import decision_from_iteration

DEFAULT_REPORT_NAME = "backtest_report.html"
_PREFERRED_BENCHMARK = "BTC/USDT"
_CHARTJS_CDN = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"


@dataclass
class _EquityPoint:
    date_short: str
    date_full: str
    equity: float
    drawdown_pct: float


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _read_trades_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _trade_pnl(t: dict[str, Any]) -> float:
    for key in ("pnl_usd", "pnl"):
        try:
            return float(t.get(key, 0) or 0)
        except (TypeError, ValueError):
            continue
    return 0.0


def _fmt_num(val: Any, *, digits: int = 2, suffix: str = "", signed: bool = False) -> str:
    if val is None or val == "":
        return "—"
    try:
        n = float(val)
    except (TypeError, ValueError):
        return html.escape(str(val))
    sign = "+" if signed and n > 0 else ""
    return f"{sign}{n:,.{digits}f}{suffix}"


def _fmt_date_short(iso_or_ts: str | int | None) -> tuple[str, str]:
    if iso_or_ts is None:
        return "—", "—"
    try:
        if isinstance(iso_or_ts, (int, float)):
            dt = datetime.fromtimestamp(float(iso_or_ts) / 1000, tz=timezone.utc)
        else:
            s = str(iso_or_ts).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%Y-%m-%d"), dt.strftime("%d %b %Y")
    except (ValueError, OSError, OverflowError):
        return str(iso_or_ts)[:10], str(iso_or_ts)


def _load_equity_curve(run_dir: Path) -> list[_EquityPoint]:
    eq_csv = run_dir / "equity_curve.csv"
    if eq_csv.is_file():
        out: list[_EquityPoint] = []
        with eq_csv.open("r", newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                try:
                    eq = float(row.get("equity", 0))
                except (TypeError, ValueError):
                    continue
                ts_raw = row.get("ts_utc") or row.get("ts_ms")
                short, full = _fmt_date_short(ts_raw if ts_raw else None)
                if short == "—":
                    short, full = str(i), str(i)
                try:
                    dd = float(row.get("drawdown_pct", 0) or 0)
                except (TypeError, ValueError):
                    dd = 0.0
                out.append(_EquityPoint(short, full, eq, dd))
        if out:
            return out

    out = []
    for i, row in enumerate(_read_jsonl(run_dir / "equity.jsonl")):
        try:
            eq = float(row.get("equity", row.get("capital", 0)))
        except (TypeError, ValueError):
            continue
        short, full = _fmt_date_short(row.get("ts"))
        out.append(_EquityPoint(short or str(i), full, eq, 0.0))
    return out


def _load_benchmark_equity(run_dir: Path, summary: dict[str, Any]) -> tuple[str, list[float]]:
    bench = summary.get("benchmark") or {}
    label = str(bench.get("benchmark_symbol") or _PREFERRED_BENCHMARK)
    initial = float(summary.get("initial_cash") or 10_000)
    n_bars = int(summary.get("total_bars") or 0)
    bars_path = run_dir / "bars.json"

    if bars_path.is_file():
        payload = json.loads(bars_path.read_text(encoding="utf-8"))
        label = str(payload.get("benchmark_symbol") or payload.get("ticker") or label)
        be = payload.get("benchmark_equity")
        if isinstance(be, list) and be:
            vals = [float(x.get("equity", 0)) for x in be if isinstance(x, dict)]
            if vals and label.upper().startswith("BTC"):
                return label, vals
        bars = payload.get("bars") or []
        if bars and label.upper().startswith("BTC"):
            vals = _price_index_equity(bars, initial)
            if vals:
                return label, vals

    if _PREFERRED_BENCHMARK in (summary.get("symbols") or [_PREFERRED_BENCHMARK]):
        cached = _benchmark_from_ohlcv_cache(summary, n_bars, initial)
        if cached:
            return _PREFERRED_BENCHMARK, cached

    if bars_path.is_file():
        payload = json.loads(bars_path.read_text(encoding="utf-8"))
        label = str(payload.get("benchmark_symbol") or payload.get("ticker") or label)
        be = payload.get("benchmark_equity")
        if isinstance(be, list) and be:
            vals = [float(x.get("equity", 0)) for x in be if isinstance(x, dict)]
            if vals:
                return label, vals
        bars = payload.get("bars") or []
        if bars:
            vals = _price_index_equity(bars, initial)
            if vals:
                return label, vals
    return label, []


def _price_index_equity(bars: list[Any], initial: float) -> list[float]:
    try:
        p0 = float(bars[0]["c"] if isinstance(bars[0], dict) else bars[0][4])
    except (TypeError, ValueError, KeyError, IndexError):
        return []
    if p0 <= 0:
        return []
    out: list[float] = []
    for b in bars:
        try:
            c = float(b["c"] if isinstance(b, dict) else b[4])
            out.append(initial * c / p0)
        except (TypeError, ValueError, KeyError, IndexError):
            continue
    return out


def _benchmark_from_ohlcv_cache(
    summary: dict[str, Any], n_bars: int, initial: float
) -> list[float]:
    if n_bars < 2:
        return []
    try:
        from backtest.ohlcv_csv_cache import ohlcv_cache_path

        tf = str(summary.get("timeframe") or "1d")
        for root in (Path("data/ohlcv"), Path(".cache/ohlcv")):
            path = ohlcv_cache_path(root, _PREFERRED_BENCHMARK, tf)
            if not path.is_file():
                continue
            rows: list[list[float]] = []
            with path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                next(reader, None)
                for parts in reader:
                    if len(parts) >= 6:
                        rows.append([float(parts[0]), float(parts[4])])
            if len(rows) < n_bars:
                continue
            tail = rows[-n_bars:]
            p0 = tail[0][1]
            if p0 <= 0:
                continue
            return [initial * r[1] / p0 for r in tail]
    except Exception:
        return []
    return []


def _align_benchmark(benchmark: list[float], n: int) -> list[float]:
    if not benchmark:
        return []
    if len(benchmark) == n:
        return benchmark
    if len(benchmark) > n:
        return benchmark[:n]
    return benchmark + [benchmark[-1]] * (n - len(benchmark))


def _daily_returns(equity: list[float]) -> list[float]:
    rets: list[float] = []
    for i in range(1, len(equity)):
        if equity[i - 1] > 0:
            rets.append((equity[i] / equity[i - 1]) - 1.0)
    return rets


def _risk_metrics(
    equity_pts: list[_EquityPoint],
    ret_pct: float | None,
    mdd: float | None,
    sharpe: float | None,
    interval_sec: int,
) -> dict[str, float | None]:
    eq = [p.equity for p in equity_pts]
    rets = _daily_returns(eq)
    bars_per_year = max(1, int(round(365 * 86400 / max(interval_sec, 60))))
    ann_factor = math.sqrt(bars_per_year)

    var_95: float | None = None
    if len(rets) >= 5:
        sorted_rets = sorted(rets)
        idx = max(0, int(math.floor(0.05 * len(sorted_rets))) - 1)
        var_95 = sorted_rets[idx] * 100.0

    calmar: float | None = None
    if ret_pct is not None and mdd and float(mdd) > 0:
        years = max(len(eq) / bars_per_year, 1 / bars_per_year)
        ann_ret = (
            ((1 + float(ret_pct) / 100.0) ** (1 / years) - 1) * 100 if years > 0 else float(ret_pct)
        )
        calmar = ann_ret / float(mdd)

    vol_ann: float | None = None
    if len(rets) >= 2:
        vol_ann = statistics.stdev(rets) * ann_factor * 100.0

    return {
        "var_95_pct": var_95,
        "calmar": calmar,
        "vol_ann_pct": vol_ann,
        "sharpe": float(sharpe) if sharpe is not None else None,
    }


def _per_symbol_attribution(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    agg: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}
    )
    for t in trades:
        sym = str(t.get("symbol") or "?")
        pnl = _trade_pnl(t)
        agg[sym]["pnl"] += pnl
        agg[sym]["trades"] += 1
        if pnl > 0:
            agg[sym]["wins"] += 1
        elif pnl < 0:
            agg[sym]["losses"] += 1
    total_pnl = sum(v["pnl"] for v in agg.values()) or 1.0
    rows = []
    for sym, v in sorted(agg.items(), key=lambda x: x[1]["pnl"], reverse=True):
        rows.append(
            {
                "symbol": sym,
                "pnl": round(v["pnl"], 2),
                "trades": v["trades"],
                "win_rate": round(100.0 * v["wins"] / max(1, v["trades"]), 1),
                "contribution_pct": round(100.0 * v["pnl"] / total_pnl, 1),
            }
        )
    return rows


def _executive_summary(
    *,
    ret_pct: float | None,
    total_bars: int,
    timeframe: str,
    leverage: Any,
    bh_pct: float | None,
    bench_label: str,
    win_rate: float | None,
    pf: float | None,
    mdd: float | None,
    trades: list[dict[str, Any]],
    quality: dict[str, Any],
) -> str:
    ret_s = _fmt_num(ret_pct, suffix="%", signed=True)
    bh_s = _fmt_num(bh_pct, suffix="%", signed=True)
    wr = _fmt_num(win_rate, suffix="%")
    pf_s = _fmt_num(pf, digits=2)
    mdd_s = _fmt_num(mdd, suffix="%")

    holds = []
    for t in trades:
        try:
            holds.append(int(t.get("holding_bars", 0) or 0))
        except (TypeError, ValueError):
            pass
    avg_hold = sum(holds) / len(holds) if holds else 0.0

    short_pnl = sum(
        _trade_pnl(t) for t in trades if str(t.get("side", "")).lower() in ("short", "sell")
    )
    long_pnl = sum(
        _trade_pnl(t) for t in trades if str(t.get("side", "")).lower() in ("long", "buy")
    )

    regimes = (quality.get("regime_coverage") or {}).get("regimes_covered") or []
    regime_txt = f" Regime coverage spanned {', '.join(regimes)}." if regimes else ""

    outperform = ""
    if isinstance(ret_pct, (int, float)) and isinstance(bh_pct, (int, float)):
        if ret_pct > bh_pct:
            outperform = (
                f" significantly outperforming {html.escape(bench_label)} buy &amp; hold ({bh_s})."
            )
        else:
            outperform = f" versus {html.escape(bench_label)} buy &amp; hold ({bh_s})."

    side_note = ""
    if short_pnl > long_pnl and short_pnl > 0:
        side_note = " Short-side execution contributed strongly during market weakness."
    elif long_pnl > short_pnl and long_pnl > 0:
        side_note = " Long-side positioning drove most of the PnL."

    hold_note = ""
    if avg_hold > 0:
        hold_note = f" Average holding period was ~{avg_hold:.1f} bars with active turnover."

    return (
        f"The strategy delivered <strong>{ret_s} return</strong> over {total_bars} "
        f"{html.escape(timeframe)} bars with {leverage}x leverage,{outperform}"
        f" Key metrics: win rate {wr}, profit factor {pf_s}, max drawdown {mdd_s}."
        f"{regime_txt}{side_note}{hold_note}"
    )


def _performance_highlights(
    trades: list[dict[str, Any]],
    quality: dict[str, Any],
    attribution: list[dict[str, Any]],
) -> str:
    items: list[str] = []
    regimes = (quality.get("regime_coverage") or {}).get("regimes_covered") or []
    if len(regimes) >= 2:
        items.append(
            f"<strong>Regime adaptation</strong> across {', '.join(html.escape(r) for r in regimes)} markets."
        )

    exit_dist = (quality.get("exit_reasons") or {}).get("distribution") or {}
    if isinstance(exit_dist, dict):
        sl = int(exit_dist.get("stop_loss", 0) or 0)
        if sl <= 10:
            items.append(f"Controlled risk with only <strong>{sl} stop-loss</strong> exits.")

    if attribution:
        top = attribution[0]
        items.append(
            f"Top contributor: <strong>{html.escape(top['symbol'])}</strong> "
            f"(${top['pnl']:,.0f}, {top['contribution_pct']:.0f}% of PnL)."
        )

    short_ct = sum(1 for t in trades if str(t.get("side", "")).lower() in ("short", "sell"))
    long_ct = sum(1 for t in trades if str(t.get("side", "")).lower() in ("long", "buy"))
    if short_ct > long_ct:
        items.append("Short bias in fill count — effective during declining benchmark window.")
    elif long_ct > short_ct:
        items.append("Long bias in fill count — captured upside legs in the window.")

    tp_ct = sum(1 for t in trades if "take_profit" in str(t.get("exit_reason", "")))
    if tp_ct:
        items.append(f"<strong>{tp_ct} take-profit</strong> exits — disciplined profit capture.")

    if not items:
        items.append("Review trade log and equity curve for path-dependent behavior.")

    return '<ul class="highlights">' + "".join(f"<li>{x}</li>" for x in items) + "</ul>"


def _params_section(rc: dict[str, Any], summary: dict[str, Any]) -> str:
    rows = [
        ("Arbitrator mode", rc.get("arbitrator_mode")),
        ("Leverage", f"{summary.get('leverage', rc.get('leverage', '—'))}x"),
        ("Take profit %", rc.get("take_profit_pct")),
        ("Stop loss %", rc.get("stop_loss_pct")),
        ("Profile ID", rc.get("profile_id") or "—"),
        ("Deploy path", rc.get("deploy_path") or "—"),
        ("Source", rc.get("source_description")),
        ("Instrument", summary.get("instrument")),
        ("Timeframe", summary.get("timeframe")),
        ("Interval", f"{summary.get('interval_sec', '—')}s"),
    ]
    body = "".join(
        f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v) if v is not None else '—')}</td></tr>"
        for k, v in rows
        if v is not None and str(v) != ""
    )
    return f'<table class="metrics-table">{body}</table>'


def _quality_section(summary: dict[str, Any]) -> str:
    qr = summary.get("quality_report") or {}
    if not qr:
        return '<p class="note">No quality report attached. Re-run with <code>run_demo</code>.</p>'

    overall = qr.get("overall_passed")
    passed = qr.get("passed_checks")
    total = qr.get("total_checks")
    score = f"{passed}/{total}" if passed is not None and total else "—"
    badge = "fail" if overall is False else ("pass" if overall else "warn")
    badge_txt = "FAILED" if overall is False else ("PASSED" if overall else "N/A")

    rows: list[tuple[str, str, str, str, str]] = []
    ss = qr.get("sample_size") or {}
    if ss:
        ok = ss.get("passed", False)
        rows.append(
            (
                "Sample size",
                "≥100 bars & ≥30 trades",
                f"{ss.get('total_bars', '?')} bars, {ss.get('trade_count', '?')} trades",
                "PASS" if ok else "FAIL",
                str(ss.get("warning") or "Use --steps 100 or --quality."),
            )
        )
    pl = qr.get("profit_loss_ratio") or {}
    if pl:
        ok = pl.get("passed", False)
        rows.append(
            (
                "Profit factor",
                f"≥ {pl.get('threshold', 1.3)}",
                _fmt_num(pl.get("profit_factor"), digits=2),
                "PASS" if ok else "FAIL",
                str(pl.get("warning") or ""),
            )
        )
    rc = qr.get("regime_coverage") or {}
    if rc:
        ok = rc.get("passed", False)
        regimes = rc.get("regimes_covered") or []
        rows.append(
            (
                "Regime coverage",
                "≥2 regimes",
                ", ".join(regimes) if regimes else "—",
                "PASS" if ok else "FAIL",
                str(rc.get("warning") or ""),
            )
        )
    er = qr.get("exit_reasons")
    if isinstance(er, dict) and er.get("passed") is not None:
        dist = er.get("pct_distribution") or {}
        top = max(dist.items(), key=lambda x: x[1])[0] if dist else "—"
        top_pct = max(dist.values()) if dist else 0
        ok = er.get("passed", False)
        rows.append(
            (
                "Exit diversity",
                "No reason &gt;80%",
                f"{top} ({top_pct:.1f}%)" if dist else "—",
                "PASS" if ok else "FAIL",
                str(er.get("warning") or ""),
            )
        )

    body = "".join(
        f"<tr><td>{html.escape(n)}</td><td>{r}</td><td>{html.escape(str(a))}</td>"
        f'<td><span class="badge {("pass" if s == "PASS" else "fail")}">{s}</span></td>'
        f'<td class="note-cell">{note}</td></tr>'
        for n, r, a, s, note in rows
    )

    why = ""
    if overall is False and ss and not ss.get("passed"):
        why = (
            '<div class="callout info"><strong>Why failed:</strong> '
            f"Only <strong>{ss.get('total_bars')} bars</strong> (need ≥100). "
            "Re-run with <code>--steps 100</code> or <code>--quality</code>.</div>"
        )
    warnings = qr.get("warnings") or []
    warn = ""
    if warnings:
        warn = (
            '<div class="callout warn"><ul>'
            + "".join(f"<li>{html.escape(str(w))}</li>" for w in warnings)
            + "</ul></div>"
        )

    return f"""
<div class="quality-header">
  <span class="badge {badge}">{badge_txt}</span>
  <span class="quality-score">Checks: <strong>{score}</strong></span>
</div>
{why}
<table class="data-table quality-table">
  <thead><tr><th>Check</th><th>Requirement</th><th>Actual</th><th>Status</th><th>Notes</th></tr></thead>
  <tbody>{body}</tbody>
</table>{warn}"""


def _decision_summary(iterations: list[dict[str, Any]]) -> Counter[str]:
    ct: Counter[str] = Counter()
    for it in iterations:
        dec = decision_from_iteration(it)
        ct[str(dec.get("action") or "HOLD")] += 1
    return ct


def build_backtest_report_html(run_dir: Path) -> str:
    run_dir = run_dir.expanduser().resolve()
    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise FileNotFoundError(f"missing summary: {summary_path}")

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    metrics = summary.get("metrics") or {}
    bench = summary.get("benchmark") or {}
    quality = summary.get("quality_report") or {}
    iterations = _read_jsonl(run_dir / "iterations.jsonl")
    trades_raw = _read_trades_csv(run_dir / "trades_record.csv")
    trades: list[dict[str, Any]] = list(trades_raw)
    if not trades:
        trades = _read_jsonl(run_dir / "trades.jsonl")

    equity_pts = _load_equity_curve(run_dir)
    bench_label, bench_vals = _load_benchmark_equity(run_dir, summary)
    bench_vals = _align_benchmark(bench_vals, len(equity_pts))
    decision_ct = _decision_summary(iterations)
    attribution = _per_symbol_attribution(trades)

    run_id = str(summary.get("run_id", run_dir.name))
    run_id_esc = html.escape(run_id)
    timeframe = str(summary.get("timeframe") or "1d")
    tf_esc = html.escape(timeframe)
    symbols = summary.get("symbols") or []
    sym_txt = html.escape(", ".join(symbols) if symbols else "—")
    total_bars = int(summary.get("total_bars") or len(equity_pts))
    trade_count = int(metrics.get("total_trades") or len(trades))
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    start_iso = str(summary.get("start_iso", equity_pts[0].date_full if equity_pts else ""))[:10]
    end_iso = str(summary.get("end_iso", equity_pts[-1].date_full if equity_pts else ""))[:10]
    initial_cash = float(summary.get("initial_cash") or 10_000)
    final_equity = float(
        summary.get("final_equity") or (equity_pts[-1].equity if equity_pts else initial_cash)
    )
    interval_sec = int(summary.get("interval_sec") or 86400)

    ret_pct = metrics.get("total_return_pct")
    bh_pct = bench.get("benchmark_buy_hold_equity_return_pct")
    if bench_vals and initial_cash > 0:
        bh_pct = (bench_vals[-1] / initial_cash - 1.0) * 100.0
    excess = (
        float(ret_pct) - float(bh_pct)
        if isinstance(ret_pct, (int, float)) and isinstance(bh_pct, (int, float))
        else bench.get("excess_return_vs_buy_hold_equity_pct")
    )
    sharpe = metrics.get("sharpe") or metrics.get("sharpe_ratio")
    sortino = metrics.get("sortino")
    mdd = metrics.get("max_drawdown_pct")
    win_rate = metrics.get("win_rate_pct") or metrics.get("win_rate")
    if isinstance(win_rate, float) and win_rate <= 1:
        win_rate = win_rate * 100
    pnl = metrics.get("total_pnl_usd")
    pf = metrics.get("profit_factor")
    fees = metrics.get("total_commission")
    rc = summary.get("resolved_config") or {}
    leverage = summary.get("leverage", rc.get("leverage", "—"))
    bench_sym_esc = html.escape(bench_label)

    risk = _risk_metrics(equity_pts, ret_pct, mdd, sharpe, interval_sec)
    period_lbl = f"{total_bars} bars ({tf_esc})" if timeframe else f"{total_bars} bars"

    chart_labels = [p.date_short for p in equity_pts]
    chart_strat = [round(p.equity, 2) for p in equity_pts]
    chart_bench = [round(v, 2) for v in bench_vals] if bench_vals else []
    chart_dd = [round(abs(p.drawdown_pct), 4) for p in equity_pts]

    chart_payload = json.dumps(
        {
            "labels": chart_labels,
            "strategy": chart_strat,
            "benchmark": chart_bench,
            "drawdown": chart_dd,
            "benchLabel": bench_label,
        }
    )

    exec_summary = _executive_summary(
        ret_pct=ret_pct if isinstance(ret_pct, (int, float)) else None,
        total_bars=total_bars,
        timeframe=timeframe,
        leverage=leverage,
        bh_pct=bh_pct if isinstance(bh_pct, (int, float)) else None,
        bench_label=bench_label,
        win_rate=win_rate if isinstance(win_rate, (int, float)) else None,
        pf=pf if isinstance(pf, (int, float)) else None,
        mdd=mdd if isinstance(mdd, (int, float)) else None,
        trades=trades,
        quality=quality,
    )
    highlights = _performance_highlights(trades, quality, attribution)
    params_html = _params_section(rc, summary)

    ret_cls = "pos" if (ret_pct or 0) >= 0 else "neg"
    mdd_cls = "neg"

    metrics_rows = [
        ("Initial Capital", f"${_fmt_num(initial_cash)}"),
        ("Final Equity", f"${_fmt_num(final_equity)}"),
        (
            "Total Return",
            f'<span class="{ret_cls}">{_fmt_num(ret_pct, suffix="%", signed=True)}</span>',
        ),
        (
            f"{bench_sym_esc} Buy & Hold",
            f'<span class="{"pos" if (bh_pct or 0) >= 0 else "neg"}">{_fmt_num(bh_pct, suffix="%", signed=True)}</span>',
        ),
        (
            "Excess Return",
            f'<span class="{"pos" if (excess or 0) >= 0 else "neg"}">{_fmt_num(excess, suffix="%", signed=True)}</span>',
        ),
        ("Sharpe Ratio", _fmt_num(sharpe, digits=2)),
        ("Sortino Ratio", _fmt_num(sortino, digits=2)),
        ("Calmar Ratio", _fmt_num(risk.get("calmar"), digits=2)),
        ("VaR (95%)", _fmt_num(risk.get("var_95_pct"), suffix="%")),
        ("Ann. Volatility", _fmt_num(risk.get("vol_ann_pct"), suffix="%")),
        ("Win Rate", f"{_fmt_num(win_rate, suffix='%')}"),
        ("Profit Factor", _fmt_num(pf, digits=2)),
        ("Max Drawdown", f'<span class="{mdd_cls}">{_fmt_num(mdd, suffix="%")}</span>'),
        ("Commissions", f"${_fmt_num(fees)}"),
        ("Total PnL", f'<span class="{ret_cls}">${_fmt_num(pnl, signed=True)}</span>'),
    ]
    metrics_table = "".join(
        f"<tr><th>{html.escape(k)}</th><td>{v}</td></tr>" for k, v in metrics_rows
    )

    max_dec = max(decision_ct.values()) if decision_ct else 1
    decision_bars = "".join(
        f'<div class="bar-row"><span class="bar-label">{html.escape(a)}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{(c / max_dec) * 100:.1f}%"></div></div>'
        f'<span class="bar-count">{c}</span></div>'
        for a, c in decision_ct.most_common()
    )

    attr_rows = "".join(
        f"<tr><td>{html.escape(r['symbol'])}</td>"
        f'<td class="{"pos" if r["pnl"] >= 0 else "neg"}">${r["pnl"]:,.2f}</td>'
        f"<td>{r['trades']}</td><td>{r['win_rate']:.1f}%</td>"
        f"<td>{r['contribution_pct']:.1f}%</td></tr>"
        for r in attribution
    )

    trade_rows = ""
    for t in trades[:300]:
        pnl_v = _trade_pnl(t)
        pnl_cls = "pos" if pnl_v > 0 else ("neg" if pnl_v < 0 else "")
        trade_rows += (
            "<tr>"
            f"<td>{html.escape(str(t.get('trade_id', '')))}</td>"
            f"<td>{html.escape(str(t.get('symbol', '')))}</td>"
            f"<td>{html.escape(str(t.get('side', '')))}</td>"
            f"<td>{html.escape(str(t.get('entry_price', '')))}</td>"
            f"<td>{html.escape(str(t.get('exit_price', '')))}</td>"
            f'<td class="{pnl_cls}">{pnl_v:,.2f}</td>'
            f"<td>{html.escape(str(t.get('holding_bars', '')))}</td>"
            f"<td>{html.escape(str(t.get('exit_reason', '')))}</td>"
            "</tr>\n"
        )

    trades_csv = "trades_record.csv" if (run_dir / "trades_record.csv").is_file() else ""
    equity_csv = "equity_curve.csv" if (run_dir / "equity_curve.csv").is_file() else ""

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Backtest Performance Report — {run_id_esc}</title>
<script src="{_CHARTJS_CDN}"></script>
<style>
:root, [data-theme="light"] {{
  --bg: #f8fafc; --card: #ffffff; --ink: #1a2332; --muted: #64748b;
  --border: #e2e8f0; --accent: #2563eb; --accent2: #0ea5e9;
  --green: #10b981; --red: #ef4444; --amber: #f59e0b; --header: #0f172a;
  --summary-bg: #f0f9ff; --table-head: #f1f5f9; --hover: #f8fafc;
  --callout-info: #eff6ff; --callout-warn: #fffbeb;
}}
[data-theme="dark"] {{
  --bg: #0f172a; --card: #1e293b; --ink: #f1f5f9; --muted: #94a3b8;
  --border: #334155; --accent: #3b82f6; --accent2: #38bdf8;
  --green: #34d399; --red: #f87171; --amber: #fbbf24; --header: #020617;
  --summary-bg: #172554; --table-head: #1e293b; --hover: #334155;
  --callout-info: #1e3a5f; --callout-warn: #422006;
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; font-family: "Inter", system-ui, -apple-system, sans-serif;
  background: var(--bg); color: var(--ink); line-height: 1.6; font-size: 14.5px;
  transition: background 0.2s, color 0.2s;
}}
.wrap {{ max-width: 1200px; margin: 0 auto; padding: 0 24px 48px; }}
.toolbar {{
  display: flex; flex-wrap: wrap; gap: 10px; justify-content: flex-end;
  padding: 12px 24px; position: sticky; top: 0; z-index: 100;
  background: var(--bg); border-bottom: 1px solid var(--border);
}}
.btn {{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px; border-radius: 8px; border: 1px solid var(--border);
  background: var(--card); color: var(--ink); font-size: 0.85rem; font-weight: 600;
  cursor: pointer; text-decoration: none; transition: background 0.15s;
}}
.btn:hover {{ background: var(--hover); }}
.btn-primary {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
.btn-primary:hover {{ opacity: 0.9; }}
header.report-header {{
  background: linear-gradient(135deg, var(--header) 0%, #1e2937 100%);
  color: #fff; padding: 40px 24px 32px; margin-bottom: 32px; border-radius: 0 0 16px 16px;
}}
header h1 {{ margin: 0 0 8px; font-size: 2rem; font-weight: 700; letter-spacing: -0.03em; }}
header .subtitle {{ opacity: 0.9; font-size: 1.05rem; }}
.meta-grid {{
  display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px; margin-top: 24px;
}}
.meta-item {{
  background: rgba(255,255,255,0.12); border-radius: 8px;
  padding: 14px 16px; backdrop-filter: blur(8px);
}}
.meta-item .lbl {{ font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; opacity: 0.85; }}
.meta-item .val {{ font-size: 1.15rem; font-weight: 700; margin-top: 4px; }}
.card {{
  background: var(--card); border: 1px solid var(--border); border-radius: 12px;
  padding: 24px 28px; margin-bottom: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
}}
.card h2 {{
  margin: 0 0 20px; font-size: 0.95rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--muted); border-bottom: 1px solid var(--border);
  padding-bottom: 12px;
}}
.grid-2 {{ display: grid; grid-template-columns: 1fr 1.35fr; gap: 24px; }}
.grid-3 {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; }}
@media (max-width: 960px) {{ .grid-2, .grid-3 {{ grid-template-columns: 1fr; }} }}
.metrics-table {{ width: 100%; border-collapse: collapse; }}
.metrics-table th {{
  text-align: left; font-weight: 500; color: var(--muted); padding: 10px 12px 10px 0;
  width: 45%; vertical-align: top;
}}
.metrics-table td {{ padding: 10px 0; font-weight: 600; }}
.chart-wrap {{ position: relative; height: 320px; margin: 12px 0; }}
.chart-wrap.sm {{ height: 180px; }}
.legend {{ display: flex; gap: 24px; margin-top: 12px; font-size: 0.9rem; color: var(--muted); flex-wrap: wrap; }}
.leg-item {{ display: flex; align-items: center; gap: 8px; }}
.swatch {{ width: 28px; height: 4px; border-radius: 2px; display: inline-block; }}
.data-table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
.data-table th {{
  text-align: left; padding: 12px 14px; background: var(--table-head); color: var(--muted);
  font-weight: 600; border-bottom: 2px solid var(--border);
}}
.data-table td {{ padding: 10px 14px; border-bottom: 1px solid var(--border); }}
.data-table tbody tr:hover {{ background: var(--hover); }}
.pos {{ color: var(--green); }}
.neg {{ color: var(--red); }}
.badge {{
  display: inline-block; padding: 4px 12px; border-radius: 6px;
  font-size: 0.78rem; font-weight: 700;
}}
.badge.pass {{ background: #dcfce7; color: #166534; }}
.badge.fail {{ background: #fee2e2; color: #991b1b; }}
.badge.warn {{ background: #fef3c7; color: #92400e; }}
[data-theme="dark"] .badge.pass {{ background: #064e3b; color: #6ee7b7; }}
[data-theme="dark"] .badge.fail {{ background: #7f1d1d; color: #fca5a5; }}
.bar-row {{ display: flex; align-items: center; gap: 16px; margin-bottom: 10px; }}
.bar-label {{ width: 60px; font-size: 0.9rem; font-weight: 600; }}
.bar-track {{ flex: 1; height: 26px; background: var(--border); border-radius: 6px; overflow: hidden; }}
.bar-fill {{ height: 100%; background: linear-gradient(90deg, var(--accent), var(--accent2)); border-radius: 6px; }}
.bar-count {{ width: 48px; text-align: right; font-size: 0.9rem; color: var(--muted); }}
.summary-box {{
  background: var(--summary-bg); border-left: 5px solid var(--accent);
  padding: 20px 24px; border-radius: 8px; font-size: 1rem; line-height: 1.7;
}}
.highlights {{ line-height: 1.75; padding-left: 20px; margin: 0; }}
.callout {{ border-radius: 8px; padding: 12px 16px; margin-bottom: 14px; font-size: 0.9rem; }}
.callout.info {{ background: var(--callout-info); border: 1px solid var(--border); }}
.callout.warn {{ background: var(--callout-warn); border: 1px solid var(--amber); }}
.quality-header {{ display: flex; align-items: center; gap: 16px; margin-bottom: 14px; }}
.note-cell {{ color: var(--muted); font-size: 0.82rem; }}
.note {{ color: var(--muted); font-size: 0.9rem; }}
footer {{ text-align: center; color: var(--muted); font-size: 0.85rem; padding: 32px 0 16px; }}
code {{ background: var(--table-head); padding: 2px 6px; border-radius: 4px; font-size: 0.85em; }}
@media print {{
  .toolbar {{ display: none; }}
  .card {{ break-inside: avoid; box-shadow: none; }}
}}
</style>
</head>
<body>
<div class="toolbar">
  <button class="btn" id="themeToggle" type="button">Dark mode</button>
  {"<a class='btn' href='trades_record.csv' download>Export trades CSV</a>" if trades_csv else ""}
  {"<a class='btn' href='equity_curve.csv' download>Export equity CSV</a>" if equity_csv else ""}
  <button class="btn btn-primary" type="button" onclick="window.print()">Print / PDF</button>
</div>

<header class="report-header">
  <div class="wrap">
    <h1>Backtest Performance Report</h1>
    <div class="subtitle">AI Market Maker • {run_id_esc} • {html.escape(start_iso)} → {html.escape(end_iso)}</div>
    <div class="meta-grid">
      <div class="meta-item"><div class="lbl">Period</div><div class="val">{html.escape(period_lbl)}</div></div>
      <div class="meta-item"><div class="lbl">Universe</div><div class="val">{sym_txt}</div></div>
      <div class="meta-item"><div class="lbl">Trades</div><div class="val">{trade_count}</div></div>
      <div class="meta-item"><div class="lbl">Total Return</div><div class="val {ret_cls}">{_fmt_num(ret_pct, suffix="%", signed=True)}</div></div>
      <div class="meta-item"><div class="lbl">Final Equity</div><div class="val">${_fmt_num(final_equity)}</div></div>
      <div class="meta-item"><div class="lbl">Max Drawdown</div><div class="val {mdd_cls}">{_fmt_num(mdd, suffix="%")}</div></div>
    </div>
  </div>
</header>

<div class="wrap">
  <div class="card">
    <h2>Executive Summary</h2>
    <div class="summary-box">{exec_summary}</div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Key Metrics</h2>
      <table class="metrics-table">{metrics_table}</table>
    </div>
    <div class="card">
      <h2>Equity Curve vs Benchmark</h2>
      <div class="chart-wrap"><canvas id="equityChart"></canvas></div>
      <div class="legend">
        <span class="leg-item"><span class="swatch" style="background:var(--accent)"></span> Strategy Equity</span>
        <span class="leg-item"><span class="swatch" style="background:var(--amber)"></span> {bench_sym_esc} Buy &amp; Hold</span>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Drawdown Profile</h2>
    <div class="chart-wrap sm"><canvas id="drawdownChart"></canvas></div>
  </div>

  <div class="grid-3">
    <div class="card">
      <h2>Strategy Parameters</h2>
      {params_html}
    </div>
    <div class="card">
      <h2>Agent Decision Distribution</h2>
      {decision_bars or '<p class="note">No iteration data.</p>'}
    </div>
    <div class="card">
      <h2>Performance Highlights</h2>
      {highlights}
    </div>
  </div>

  <div class="grid-2">
    <div class="card">
      <h2>Performance Attribution</h2>
      <table class="data-table">
        <thead><tr><th>Symbol</th><th>PnL</th><th>Trades</th><th>Win%</th><th>Contrib.</th></tr></thead>
        <tbody>{attr_rows or '<tr><td colspan="5" class="note">No trades</td></tr>'}</tbody>
      </table>
    </div>
    <div class="card">
      <h2>Quality Gates</h2>
      {_quality_section(summary)}
    </div>
  </div>

  <div class="card">
    <h2>Trade Log ({trade_count} fills)</h2>
    <div style="overflow-x:auto">
      <table class="data-table">
        <thead><tr>
          <th>ID</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th>
          <th>PnL (USD)</th><th>Bars</th><th>Reason</th>
        </tr></thead>
        <tbody>{trade_rows or '<tr><td colspan="8" class="note">No trades</td></tr>'}</tbody>
      </table>
    </div>
  </div>
</div>

<footer>AI Market Maker Backtest Report • {run_id_esc} • Generated {generated}</footer>

<script>
const REPORT_DATA = {chart_payload};
const isDark = () => document.documentElement.getAttribute('data-theme') === 'dark';
const gridColor = () => isDark() ? 'rgba(148,163,184,0.2)' : 'rgba(100,116,139,0.15)';
const textColor = () => isDark() ? '#94a3b8' : '#64748b';

function buildCharts() {{
  const d = REPORT_DATA;
  const eqCtx = document.getElementById('equityChart');
  const ddCtx = document.getElementById('drawdownChart');
  const datasets = [{{
    label: 'Strategy',
    data: d.strategy,
    borderColor: '#2563eb',
    backgroundColor: 'rgba(37,99,235,0.08)',
    fill: true,
    tension: 0.2,
    pointRadius: 0,
    borderWidth: 2.5,
  }}];
  if (d.benchmark && d.benchmark.length) {{
    datasets.push({{
      label: d.benchLabel + ' B&H',
      data: d.benchmark,
      borderColor: '#f59e0b',
      borderDash: [6, 4],
      fill: false,
      tension: 0.2,
      pointRadius: 0,
      borderWidth: 2,
    }});
  }}
  window._equityChart = new Chart(eqCtx, {{
    type: 'line',
    data: {{ labels: d.labels, datasets }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{
          callbacks: {{
            label: (ctx) => ctx.dataset.label + ': $' + ctx.parsed.y.toLocaleString(undefined, {{maximumFractionDigits: 0}}),
          }},
        }},
      }},
      scales: {{
        x: {{
          ticks: {{ maxTicksLimit: 8, color: textColor() }},
          grid: {{ color: gridColor() }},
        }},
        y: {{
          ticks: {{
            color: textColor(),
            callback: (v) => '$' + Number(v).toLocaleString(undefined, {{maximumFractionDigits: 0}}),
          }},
          grid: {{ color: gridColor() }},
        }},
      }},
    }},
  }});
  window._ddChart = new Chart(ddCtx, {{
    type: 'line',
    data: {{
      labels: d.labels,
      datasets: [{{
        label: 'Drawdown %',
        data: d.drawdown,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239,68,68,0.12)',
        fill: true,
        tension: 0.2,
        pointRadius: 0,
        borderWidth: 1.5,
      }}],
    }},
    options: {{
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ maxTicksLimit: 6, color: textColor() }}, grid: {{ display: false }} }},
        y: {{
          reverse: false,
          ticks: {{ color: textColor(), callback: (v) => '-' + v + '%' }},
          grid: {{ color: gridColor() }},
        }},
      }},
    }},
  }});
}}

document.getElementById('themeToggle').addEventListener('click', () => {{
  const root = document.documentElement;
  const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  root.setAttribute('data-theme', next);
  localStorage.setItem('aimm-report-theme', next);
  document.getElementById('themeToggle').textContent = next === 'dark' ? 'Light mode' : 'Dark mode';
  if (window._equityChart) window._equityChart.destroy();
  if (window._ddChart) window._ddChart.destroy();
  buildCharts();
}});

const saved = localStorage.getItem('aimm-report-theme');
if (saved === 'dark') {{
  document.documentElement.setAttribute('data-theme', 'dark');
  document.getElementById('themeToggle').textContent = 'Light mode';
}}
buildCharts();
</script>
</body>
</html>"""


def write_backtest_report_html(
    run_dir: Path | str,
    *,
    output_name: str = DEFAULT_REPORT_NAME,
) -> Path:
    run_dir = Path(run_dir).expanduser().resolve()
    out_path = run_dir / output_name
    out_path.write_text(build_backtest_report_html(run_dir), encoding="utf-8")
    return out_path
