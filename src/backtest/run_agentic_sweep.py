"""Agentic parameter sweep across regimes, symbol sets, and arbitrator/TA presets.

Deterministic weighted arbitrator only (no LLM). Writes::

    .runs/evaluations/sweep_<id>/sweep_report.json
    .runs/evaluations/sweep_<id>/sweep_report.md

Example::

    NEXUS_DISABLE=1 uv run python -m backtest.run_agentic_sweep

    uv run python -m backtest.run_agentic_sweep --quick
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from backtest.bars import (
    align_bars_by_min_length,
    fetch_ccxt_ohlcv_bars,
    fetch_ccxt_ohlcv_range,
    iso_utc_to_ms,
    nominal_interval_sec_for_timeframe,
)
from backtest.historical_eval import HistoryWindowSpec, compute_regime_check
from backtest.loop import run_multi_step_backtest
from config.fund_policy import load_fund_policy


@dataclass(frozen=True)
class SymbolSet:
    id: str
    symbols: tuple[str, ...]
    benchmark: str


@dataclass(frozen=True)
class AgenticPreset:
    id: str
    label: str
    profile_weights: dict[str, float] | None
    decision_threshold: dict[str, Any] | None


# Mirrors ``_V4_DECISION_THRESHOLD`` in weighted_arbitrator (offline sweep variants only).
_THR_BASE: dict[str, Any] = {
    "buy": {"min_composite": 53, "min_confidence": 16},
    "sell": {"max_composite": 41, "min_confidence": 26},
    "hold": {"else": True},
    "alignment_gating": {
        "enabled": True,
        "min_factors_for_directional": 2,
        "risk_override_if_blocked": True,
    },
    "ta_led": {
        "enabled": True,
        "agent_id": "2.3",
        "buy_min_composite": 57,
        "sell_max_composite": 43,
        "min_confidence": 14,
    },
}


def _thr(**patch: Any) -> dict[str, Any]:
    """Deep-copy base threshold and apply shallow patches (ta_led, buy, sell, …)."""
    out = copy.deepcopy(_THR_BASE)
    for key, val in patch.items():
        if isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **val}
        else:
            out[key] = val
    return out


SHOWCASE_WINDOWS: tuple[HistoryWindowSpec, ...] = (
    HistoryWindowSpec(
        id="bear_2022_h1",
        label="Bear 2022 H1 (macro tightening)",
        since="2022-01-01",
        until="2022-06-30",
    ),
    HistoryWindowSpec(
        id="bull_2023_h2",
        label="Bull 2023 H2 (ETF anticipation rally)",
        since="2023-07-01",
        until="2023-12-31",
    ),
    HistoryWindowSpec(
        id="bull_2024_h1",
        label="Bull 2024 H1 (post-ETF momentum)",
        since="2024-01-01",
        until="2024-06-30",
    ),
    HistoryWindowSpec(
        id="sideways_2023_h1",
        label="Sideways 2023 H1 (range / recovery chop)",
        since="2023-01-01",
        until="2023-06-30",
    ),
)


REGIME_WINDOWS: tuple[HistoryWindowSpec, ...] = (
    HistoryWindowSpec(
        id="bear_2022_h2",
        label="Bear 2022 H2 (post-Luna / FTX)",
        since="2022-07-01",
        until="2022-12-31",
    ),
    HistoryWindowSpec(
        id="bear_2022_h1",
        label="Bear 2022 H1 (macro tightening)",
        since="2022-01-01",
        until="2022-06-30",
    ),
    HistoryWindowSpec(
        id="bull_2023_h2",
        label="Bull 2023 H2 (ETF anticipation rally)",
        since="2023-07-01",
        until="2023-12-31",
    ),
    HistoryWindowSpec(
        id="bull_2024_h1",
        label="Bull 2024 H1 (post-ETF momentum)",
        since="2024-01-01",
        until="2024-06-30",
    ),
    HistoryWindowSpec(
        id="sideways_2023_h1",
        label="Sideways 2023 H1 (range / recovery chop)",
        since="2023-01-01",
        until="2023-06-30",
    ),
)

SYMBOL_SETS: tuple[SymbolSet, ...] = (
    SymbolSet("btc", ("BTC/USDT",), "BTC/USDT"),
    SymbolSet("majors3", ("BTC/USDT", "ETH/USDT", "SOL/USDT"), "BTC/USDT"),
    SymbolSet("majors4_vcp", ("BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"), "BTC/USDT"),
)

PRESETS: tuple[AgenticPreset, ...] = (
    AgenticPreset(
        id="github_default",
        label="Shipped default (2.3@0.55, 1.1@0.25, ta_led 57/43)",
        profile_weights=None,
        decision_threshold=None,
    ),
    AgenticPreset(
        id="ta_heavy_75",
        label="TA-heavy desk (2.3@0.75, ta_led 55/44)",
        profile_weights={"2.3": 0.75, "2.1": 0.10, "1.1": 0.10},
        decision_threshold=_thr(ta_led={"buy_min_composite": 55, "sell_max_composite": 44}),
    ),
    AgenticPreset(
        id="balanced_desk",
        label="Balanced TA + pattern (2.3@0.55, 2.1@0.25, global 54/18)",
        profile_weights={"2.3": 0.55, "2.1": 0.25, "1.1": 0.15},
        decision_threshold=_thr(buy={"min_composite": 54, "min_confidence": 18}),
    ),
    AgenticPreset(
        id="conservative_gate",
        label="Conservative gates (2.3@0.60, ta_led 59/41)",
        profile_weights={"2.3": 0.60, "2.1": 0.20, "1.1": 0.15},
        decision_threshold=_thr(ta_led={"buy_min_composite": 59, "sell_max_composite": 41}),
    ),
    AgenticPreset(
        id="convergence_only",
        label="Global convergence only (ta_led off)",
        profile_weights=None,
        decision_threshold=_thr(ta_led={"enabled": False}),
    ),
    AgenticPreset(
        id="pattern_assist",
        label="Pattern-assist blend (2.1@0.30, 2.3@0.50)",
        profile_weights={"2.3": 0.50, "2.1": 0.30, "1.1": 0.15},
        decision_threshold=None,
    ),
    AgenticPreset(
        id="macro_tilt",
        label="Macro tilt (1.1@0.25, 2.3@0.55)",
        profile_weights={"2.3": 0.55, "2.1": 0.15, "1.1": 0.25},
        decision_threshold=None,
    ),
    AgenticPreset(
        id="aggressive_ta",
        label="Aggressive TA (2.3@0.70, ta_led 54/44, buy 51)",
        profile_weights={"2.3": 0.70, "2.1": 0.12, "1.1": 0.10},
        decision_threshold=_thr(
            buy={"min_composite": 51, "min_confidence": 15},
            ta_led={"buy_min_composite": 54, "sell_max_composite": 44, "min_confidence": 12},
        ),
    ),
    AgenticPreset(
        id="strict_align",
        label="Strict alignment (min 3 factors, ta_led 58/42)",
        profile_weights={"2.3": 0.65, "2.1": 0.15, "1.1": 0.10},
        decision_threshold=_thr(
            alignment_gating={"enabled": True, "min_factors_for_directional": 3},
            ta_led={"buy_min_composite": 58, "sell_max_composite": 42},
        ),
    ),
)


def _btc_buy_hold_return_pct(bars: list[list[float]]) -> float | None:
    if len(bars) < 2:
        return None
    c0 = float(bars[0][4])
    c1 = float(bars[-1][4])
    if c0 <= 0:
        return None
    return round((c1 / c0 - 1.0) * 100.0, 4)


def _fetch_window_bars(
    spec: HistoryWindowSpec,
    symbols: tuple[str, ...],
    *,
    exchange: str,
) -> dict[str, list[list[float]]]:
    since_ms = iso_utc_to_ms(spec.since)
    until_ms = iso_utc_to_ms(spec.until) + 86_400_000 - 1
    out: dict[str, list[list[float]]] = {}
    for sym in symbols:
        out[sym] = fetch_ccxt_ohlcv_range(
            sym,
            timeframe=spec.timeframe,
            since_ms=since_ms,
            until_ms=until_ms,
            exchange_id=exchange,
        )
    aligned = align_bars_by_min_length(out)
    return {k: [list(row) for row in v] for k, v in aligned.items()}


def _fetch_tail_bars(
    symbols: tuple[str, ...],
    *,
    steps: int,
    timeframe: str,
    exchange: str,
) -> dict[str, list[list[float]]]:
    out: dict[str, list[list[float]]] = {}
    for sym in symbols:
        out[sym] = fetch_ccxt_ohlcv_bars(
            sym, limit=steps + 5, timeframe=timeframe, exchange_id=exchange
        )
    aligned = align_bars_by_min_length(out)
    trimmed = {k: v[-steps:] if len(v) > steps else v for k, v in aligned.items()}
    return {k: [list(row) for row in v] for k, v in trimmed.items()}


def _apply_sweep_env() -> dict[str, str | None]:
    """Ensure Nexus-off for OHLCV-only sweep; LLM key required (no mode toggle)."""
    prior: dict[str, str | None] = {}
    for key, val in (("NEXUS_DISABLE", "1"),):
        prior[key] = os.environ.get(key)
        os.environ[key] = val
    return prior


def _restore_env(prior: dict[str, str | None]) -> None:
    for key, val in prior.items():
        if val is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = val


def _run_one(
    *,
    window_id: str,
    window_label: str,
    bars_by_symbol: dict[str, list[list[float]]],
    sym_set: SymbolSet,
    preset: AgenticPreset,
    initial_cash: float,
    runs_dir: Path,
    sweep_id: str,
    tp_sl_pct: float,
) -> dict[str, Any]:
    bench_bars = bars_by_symbol.get(sym_set.benchmark, [])
    interval_sec = (
        max(60, int((bench_bars[1][0] - bench_bars[0][0]) / 1000))
        if len(bench_bars) >= 2
        else nominal_interval_sec_for_timeframe("1d")
    )
    run_id = f"{sweep_id}_{window_id}_{sym_set.id}_{preset.id}"
    prior = _apply_sweep_env()
    deploy_cfg: dict[str, Any] = {}
    if preset.profile_weights:
        deploy_cfg["profile_weights"] = dict(preset.profile_weights)
    if preset.decision_threshold:
        deploy_cfg["decision_threshold"] = copy.deepcopy(preset.decision_threshold)
    try:
        if len(sym_set.symbols) == 1:
            res = run_multi_step_backtest(
                ticker=sym_set.benchmark,
                bars=bench_bars,
                initial_cash=initial_cash,
                interval_sec=interval_sec,
                run_id=run_id,
                runs_dir=runs_dir,
                export_bundle=False,
                take_profit_pct=tp_sl_pct,
                stop_loss_pct=tp_sl_pct,
                deploy_profile_weights=preset.profile_weights,
                deploy_arbitrator_mode="agent_llm",
                deploy_config=deploy_cfg or None,
                timeframe="1d",
            )
        else:
            res = run_multi_step_backtest(
                ticker=sym_set.benchmark,
                bars_by_symbol=bars_by_symbol,
                initial_cash=initial_cash,
                interval_sec=interval_sec,
                run_id=run_id,
                runs_dir=runs_dir,
                export_bundle=False,
                take_profit_pct=tp_sl_pct,
                stop_loss_pct=tp_sl_pct,
                deploy_profile_weights=preset.profile_weights,
                deploy_arbitrator_mode="agent_llm",
                deploy_config=deploy_cfg or None,
                timeframe="1d",
            )
    finally:
        _restore_env(prior)

    m = res.metrics or {}
    bench = res.benchmark or {}
    bh = _btc_buy_hold_return_pct(bench_bars)
    regime = compute_regime_check(bench_bars)
    return {
        "run_id": run_id,
        "window_id": window_id,
        "window_label": window_label,
        "symbol_set": sym_set.id,
        "symbols": list(sym_set.symbols),
        "preset": preset.id,
        "preset_label": preset.label,
        "bars": len(bench_bars),
        "btc_buy_hold_return_pct": bh,
        "total_return_pct": m.get("total_return_pct"),
        "excess_vs_btc_bh_pct": bench.get("excess_return_vs_buy_hold_equity_pct"),
        "trade_count": m.get("total_trades", 0),
        "profit_factor": m.get("profit_factor"),
        "sharpe": m.get("sharpe"),
        "max_drawdown_pct": m.get("max_drawdown_pct"),
        "win_rate_pct": m.get("win_rate_pct"),
        "regimes_in_window": regime.get("regimes_covered"),
        "quality_passed": (res.quality_report or {}).get("overall_passed"),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_preset: dict[str, list[dict[str, Any]]] = {}
    by_window: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_preset.setdefault(str(r["preset"]), []).append(r)
        by_window.setdefault(str(r["window_id"]), []).append(r)

    def _mean(vals: list[float]) -> float | None:
        return round(sum(vals) / len(vals), 4) if vals else None

    preset_summary = {}
    for pid, grp in by_preset.items():
        rets = [float(x["total_return_pct"]) for x in grp if x.get("total_return_pct") is not None]
        excess = [
            float(x["excess_vs_btc_bh_pct"])
            for x in grp
            if x.get("excess_vs_btc_bh_pct") is not None
        ]
        trades = [int(x.get("trade_count") or 0) for x in grp]
        preset_summary[pid] = {
            "runs": len(grp),
            "mean_return_pct": _mean(rets),
            "mean_excess_vs_btc_pct": _mean(excess),
            "mean_trades": _mean([float(t) for t in trades]),
            "positive_return_windows": sum(1 for v in rets if v > 0),
            "beat_btc_windows": sum(1 for v in excess if v > 0),
        }

    return {
        "total_runs": len(rows),
        "by_preset": preset_summary,
        "best_by_excess": sorted(
            rows,
            key=lambda x: float(x.get("excess_vs_btc_bh_pct") or -999),
            reverse=True,
        )[:8],
        "worst_by_return": sorted(
            rows,
            key=lambda x: float(x.get("total_return_pct") or 999),
        )[:5],
    }


def _github_default_pick(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Score presets for README/showcase default (majors3, balanced across regimes)."""
    majors = [r for r in rows if r.get("symbol_set") == "majors3"]
    by_preset: dict[str, list[dict[str, Any]]] = {}
    for r in majors:
        by_preset.setdefault(str(r["preset"]), []).append(r)

    scored: list[dict[str, Any]] = []
    for pid, grp in by_preset.items():
        rets = [float(x["total_return_pct"]) for x in grp if x.get("total_return_pct") is not None]
        excess = [
            float(x["excess_vs_btc_bh_pct"])
            for x in grp
            if x.get("excess_vs_btc_bh_pct") is not None
        ]
        trades = [int(x.get("trade_count") or 0) for x in grp]
        if not rets:
            continue
        mean_ret = sum(rets) / len(rets)
        mean_excess = sum(excess) / len(excess) if excess else -999.0
        mean_trades = sum(trades) / len(trades) if trades else 0.0
        pos = sum(1 for v in rets if v > 0)
        beat = sum(1 for v in excess if v > 0)
        crash_penalty = sum(min(0.0, v) for v in rets) * 0.15
        score = mean_excess + pos * 3.0 + beat * 2.0 + min(mean_trades, 40) * 0.05 + crash_penalty
        scored.append(
            {
                "preset": pid,
                "score": round(score, 4),
                "mean_return_pct": round(mean_ret, 4),
                "mean_excess_vs_btc_pct": round(mean_excess, 4),
                "mean_trades": round(mean_trades, 2),
                "positive_windows": pos,
                "beat_btc_windows": beat,
                "runs": len(grp),
            }
        )
    scored.sort(key=lambda x: float(x["score"]), reverse=True)
    best_row = None
    if scored:
        top = scored[0]["preset"]
        candidates = [r for r in majors if r.get("preset") == top]
        candidates.sort(
            key=lambda x: float(x.get("excess_vs_btc_bh_pct") or -999),
            reverse=True,
        )
        best_row = candidates[0] if candidates else None
    return {"ranked": scored, "recommended_showcase_run": best_row}


def _report_md(report: dict[str, Any]) -> str:
    lines = [
        "# Agentic parameter sweep",
        "",
        f"- Sweep ID: `{report['sweep_id']}`",
        f"- Runs: {report['aggregate']['total_runs']}",
        "",
        "## Preset summary (mean across windows × symbol sets)",
        "",
        "| Preset | Mean return % | Mean excess vs BTC % | Mean trades | Beat BTC |",
        "|--------|---------------|----------------------|-------------|----------|",
    ]
    for pid, s in report["aggregate"]["by_preset"].items():
        lines.append(
            f"| {pid} | {s.get('mean_return_pct')} | {s.get('mean_excess_vs_btc_pct')} | "
            f"{s.get('mean_trades')} | {s.get('beat_btc_windows')}/{s.get('runs')} |"
        )
    lines.extend(["", "## Top runs by excess return vs BTC", ""])
    for r in report["aggregate"]["best_by_excess"]:
        lines.append(
            f"- **{r['preset']}** / {r['window_id']} / {r['symbol_set']}: "
            f"return {r.get('total_return_pct')}% vs BTC {r.get('btc_buy_hold_return_pct')}% "
            f"(excess {r.get('excess_vs_btc_bh_pct')}%), trades={r.get('trade_count')}, "
            f"PF={r.get('profit_factor')}"
        )
    rec = report.get("github_default_recommendation") or {}
    ranked = rec.get("ranked") or []
    if ranked:
        lines.extend(["", "## GitHub default recommendation (majors3 scoring)", ""])
        lines.append(
            "Scoring favors mean excess vs BTC, windows with positive return, "
            "and penalizes deep drawdown windows. All presets are agentic "
            "(weighted arbitrator + TA 2.3); no momentum fallback."
        )
        lines.append("")
        lines.append("| Rank | Preset | Score | Mean excess % | Mean return % | Beat BTC |")
        lines.append("|------|--------|-------|---------------|---------------|----------|")
        for i, row in enumerate(ranked[:5], 1):
            lines.append(
                f"| {i} | {row['preset']} | {row['score']} | {row['mean_excess_vs_btc_pct']} | "
                f"{row['mean_return_pct']} | {row['beat_btc_windows']}/{row['runs']} |"
            )
        showcase = rec.get("recommended_showcase_run")
        if showcase:
            lines.extend(
                [
                    "",
                    "### Suggested README showcase command",
                    "",
                    "```bash",
                    "NEXUS_DISABLE=1 uv run python -m backtest.run_demo --online \\",
                    f"  --timeframe 1d --steps {showcase.get('bars', 365)} \\",
                    "  --symbols BTC/USDT,ETH/USDT,SOL/USDT --ticker BTC/USDT",
                    "```",
                    "",
                    f"- Preset: `{showcase.get('preset')}` "
                    f"(offline sweep only; shipped repo default = `github_default`)",
                    f"- Window: **{showcase.get('window_label')}** (`{showcase.get('window_id')}`)",
                    f"- Reference result: return **{showcase.get('total_return_pct')}%**, "
                    f"excess vs BTC **{showcase.get('excess_vs_btc_bh_pct')}%**, "
                    f"trades={showcase.get('trade_count')}, PF={showcase.get('profit_factor')}",
                ]
            )
    lines.extend(
        [
            "",
            "## All runs",
            "",
            "| Window | Symbols | Preset | Return % | BTC B&H % | Excess % | Trades | PF |",
            "|--------|---------|--------|----------|-----------|----------|--------|-----|",
        ]
    )
    for r in report["rows"]:
        lines.append(
            f"| {r['window_id']} | {r['symbol_set']} | {r['preset']} | "
            f"{r.get('total_return_pct')} | {r.get('btc_buy_hold_return_pct')} | "
            f"{r.get('excess_vs_btc_bh_pct')} | {r.get('trade_count')} | {r.get('profit_factor')} |"
        )
    return "\n".join(lines) + "\n"


def run_sweep(
    *,
    windows: tuple[HistoryWindowSpec, ...],
    symbol_sets: tuple[SymbolSet, ...],
    presets: tuple[AgenticPreset, ...],
    runs_dir: Path,
    initial_cash: float,
    exchange: str,
    tp_sl_pct: float,
    tail_steps: int | None,
) -> dict[str, Any]:
    sweep_id = f"sweep_{int(time.time())}"
    out_dir = runs_dir / "evaluations" / sweep_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    total = len(windows) * len(symbol_sets) * len(presets) + (
        len(symbol_sets) * len(presets) if tail_steps else 0
    )
    n = 0
    for spec in windows:
        print(f"[sweep] fetching {spec.id} ({spec.since} → {spec.until})…", file=sys.stderr)
        for sym_set in symbol_sets:
            try:
                bars_map = _fetch_window_bars(spec, sym_set.symbols, exchange=exchange)
            except Exception as exc:
                print(f"[sweep] skip {spec.id}/{sym_set.id}: fetch failed: {exc}", file=sys.stderr)
                continue
            if not bars_map.get(sym_set.benchmark):
                continue
            for preset in presets:
                n += 1
                print(
                    f"[sweep] ({n}/{total}) {spec.id} {sym_set.id} {preset.id}",
                    file=sys.stderr,
                )
                row = _run_one(
                    window_id=spec.id,
                    window_label=spec.label,
                    bars_by_symbol=bars_map,
                    sym_set=sym_set,
                    preset=preset,
                    initial_cash=initial_cash,
                    runs_dir=runs_dir,
                    sweep_id=sweep_id,
                    tp_sl_pct=tp_sl_pct,
                )
                rows.append(row)
                print(
                    f"  → return {row.get('total_return_pct')}% excess {row.get('excess_vs_btc_bh_pct')}% "
                    f"trades={row.get('trade_count')}",
                    file=sys.stderr,
                )

    if tail_steps:
        print(f"[sweep] fetching tail {tail_steps}d…", file=sys.stderr)
        for sym_set in symbol_sets:
            try:
                bars_map = _fetch_tail_bars(
                    sym_set.symbols, steps=tail_steps, timeframe="1d", exchange=exchange
                )
            except Exception as exc:
                print(f"[sweep] skip tail/{sym_set.id}: {exc}", file=sys.stderr)
                continue
            for preset in presets:
                n += 1
                print(f"[sweep] ({n}) tail_{tail_steps}d {sym_set.id} {preset.id}", file=sys.stderr)
                row = _run_one(
                    window_id=f"tail_{tail_steps}d",
                    window_label=f"Recent {tail_steps} daily bars",
                    bars_by_symbol=bars_map,
                    sym_set=sym_set,
                    preset=preset,
                    initial_cash=initial_cash,
                    runs_dir=runs_dir,
                    sweep_id=sweep_id,
                    tp_sl_pct=tp_sl_pct,
                )
                rows.append(row)

    report = {
        "sweep_id": sweep_id,
        "methodology": (
            "Deterministic weighted arbitrator; hold_signal_fallback=off; "
            "TA momentum via agent 2.3 ta_bundle/v2; presets vary profile_weights "
            "and decision_threshold via deploy_config only (no new env flags)."
        ),
        "rows": rows,
        "aggregate": _aggregate(rows),
        "github_default_recommendation": _github_default_pick(rows),
    }
    (out_dir / "sweep_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "sweep_report.md").write_text(_report_md(report), encoding="utf-8")
    return report


def main() -> None:
    load_dotenv(override=True)
    parser = argparse.ArgumentParser(description="Agentic parameter / regime sweep.")
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument("--runs-dir", type=Path, default=Path(".runs"))
    parser.add_argument(
        "--showcase",
        action="store_true",
        help="Focused grid: 4 regime windows + tail 180d, majors3 only, all presets.",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Smaller grid: 3 windows, btc+majors3, all presets.",
    )
    parser.add_argument(
        "--tail-steps",
        type=int,
        default=180,
        help="Also run recent N daily bars (0 to disable). Default 180.",
    )
    args = parser.parse_args()

    fp = load_fund_policy()
    tp_sl = float(fp.take_profit_pct) * 100.0

    windows = REGIME_WINDOWS
    symbol_sets = SYMBOL_SETS
    if args.showcase:
        windows = SHOWCASE_WINDOWS
        symbol_sets = (SYMBOL_SETS[1],)  # majors3
    elif args.quick:
        windows = (
            REGIME_WINDOWS[0],  # bear_2022_h2
            REGIME_WINDOWS[2],  # bull_2023_h2
            REGIME_WINDOWS[4],  # sideways_2023_h1
        )
        symbol_sets = (SYMBOL_SETS[0], SYMBOL_SETS[1])

    tail = args.tail_steps if args.tail_steps > 0 else None
    report = run_sweep(
        windows=windows,
        symbol_sets=symbol_sets,
        presets=PRESETS,
        runs_dir=args.runs_dir,
        initial_cash=args.initial_cash,
        exchange=args.exchange,
        tp_sl_pct=tp_sl,
        tail_steps=tail,
    )
    out = args.runs_dir / "evaluations" / report["sweep_id"]
    print(json.dumps({"sweep_id": report["sweep_id"], "report_dir": str(out)}, indent=2))
    print(f"[sweep] wrote {out / 'sweep_report.md'}", file=sys.stderr)


if __name__ == "__main__":
    main()
