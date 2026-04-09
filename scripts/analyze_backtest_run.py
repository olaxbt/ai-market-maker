#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from backtest.exchange_trade_format import (  # noqa: E402
    trade_row_fee_usd,
    trade_row_side,
    trade_row_symbol_for_analytics,
)


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


@dataclass(frozen=True)
class RunPaths:
    root: Path
    summary: Path
    trades: Path
    iterations: Path


def _paths(run_dir: Path) -> RunPaths:
    return RunPaths(
        root=run_dir,
        summary=run_dir / "summary.json",
        trades=run_dir / "trades.jsonl",
        iterations=run_dir / "iterations.jsonl",
    )


STABLE_HINTS = ("USDC/USDT", "USD1/USDT", "FDUSD/USDT", "TUSD/USDT", "USDP/USDT")


def _is_stable_pair(sym: str) -> bool:
    s = (sym or "").upper()
    return any(h.replace("/", "").upper() in s.replace("/", "").upper() for h in STABLE_HINTS)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Summarize a persisted backtest (summary.json, trades.jsonl, iterations.jsonl).",
        epilog=(
            "Example: uv run python scripts/analyze_backtest_run.py "
            "--run-dir .runs/backtests/my_run_id"
        ),
    )
    ap.add_argument(
        "--run-dir",
        required=True,
        help="Directory for one run: .runs/backtests/<run_id> (contains summary.json)",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    p = _paths(run_dir)
    if not p.summary.exists():
        raise SystemExit(f"missing summary: {p.summary}")
    if not p.trades.exists():
        raise SystemExit(f"missing trades: {p.trades}")
    if not p.iterations.exists():
        raise SystemExit(f"missing iterations: {p.iterations}")

    summary = json.loads(p.summary.read_text(encoding="utf-8"))
    bench = summary.get("benchmark") or {}
    print(f"run_id: {summary.get('run_id')}")
    print(f"steps: {summary.get('steps')}  trades: {summary.get('trade_count')}")
    print(
        f"return_pct: {bench.get('strategy_total_return_pct')}  "
        f"btc_bh_pct: {bench.get('benchmark_buy_hold_equity_return_pct')}  "
        f"eqw_bh_pct: {bench.get('benchmark_equal_weight_equity_return_pct')}"
    )
    print("")

    fee_total = 0.0
    side_ct = Counter()
    sym_ct = Counter()
    sym_fee = defaultdict(float)
    reason_cat = Counter()
    forced = 0
    stable_trades = 0

    for tr in _read_jsonl(p.trades):
        sym = trade_row_symbol_for_analytics(tr)
        side = trade_row_side(tr)
        fee = trade_row_fee_usd(tr)
        fee_total += fee
        side_ct[side] += 1
        sym_ct[sym] += 1
        sym_fee[sym] += fee
        if _is_stable_pair(sym):
            stable_trades += 1
        meta = tr.get("_sim") if isinstance(tr.get("_sim"), dict) else {}
        legacy = tr.get("reason") if isinstance(tr.get("reason"), dict) else {}
        cat = str(meta.get("category") or legacy.get("category") or "")
        if cat:
            reason_cat[cat] += 1
            forced_by = str(meta.get("forced_by") or legacy.get("forced_by") or "")
            if forced_by == "backtest_engine":
                forced += 1

    it_action = Counter()
    it_conf = []
    it_llm = False
    for it in _read_jsonl(p.iterations):
        ti = it.get("trade_intent") if isinstance(it.get("trade_intent"), dict) else {}
        it_action[str(ti.get("action") or "HOLD")] += 1
        c = ti.get("confidence")
        if isinstance(c, (int, float)):
            it_conf.append(float(c))
        it_llm = bool(it_llm or it.get("llm_arbitrator") is True)

    print(f"llm_arbitrator: {it_llm}")
    print(f"fees_usd_total: {fee_total:.2f}")
    if stable_trades:
        print(
            f"stable_pair_trades: {stable_trades} ({stable_trades / max(1, sum(side_ct.values())):.1%})"
        )
    print(f"sides: {dict(side_ct)}")
    if forced:
        print(f"forced_exits: {forced} ({forced / max(1, sum(sym_ct.values())):.1%} of fills)")
    if reason_cat:
        top_reasons = dict(reason_cat.most_common(6))
        print(f"top_reason_categories: {top_reasons}")
    print(f"trade_intent_actions_by_step: {dict(it_action)}")
    if it_conf:
        avg_c = sum(it_conf) / len(it_conf)
        above = sum(1 for x in it_conf if x >= 0.55)
        print(f"trade_intent_conf_avg: {avg_c:.3f}  steps_conf>=0.55: {above}/{len(it_conf)}")

    # Per-symbol activity snapshot (top 8)
    print("")
    print("top_symbols_by_fills:")
    for sym, ct in sym_ct.most_common(8):
        print(f"  {sym}: fills={ct} fee_usd={sym_fee[sym]:.2f}")


if __name__ == "__main__":
    main()
