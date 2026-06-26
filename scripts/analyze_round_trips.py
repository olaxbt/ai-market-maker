#!/usr/bin/env python3
"""Round-trip analysis: join trades.csv with agent stance from iterations.jsonl.

Output per-trade report with:
- Entry/exit prices, PnL, holding bars
- Agent stance (BUY/SELL/HOLD) at entry bar
- Agent confidence at entry bar
- Exit reason breakdown
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from backtest.iteration_decision import decision_from_iteration  # noqa: E402


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def _read_trades_csv(path: Path) -> list[dict[str, Any]]:
    """Read trades_record.csv into list of dicts."""
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Round-trip analysis: join trades.csv with agent stance at entry.",
        epilog=(
            "Example:\n"
            "  uv run python scripts/analyze_round_trips.py \\\n"
            "    --run-dir .runs/backtests/bt_12345\n"
        ),
    )
    ap.add_argument(
        "--run-dir",
        required=True,
        help="Run directory containing summary.json, trades_record.csv, iterations.jsonl",
    )
    ap.add_argument(
        "--csv",
        action="store_true",
        help="Output trades_record.csv with stance columns appended",
    )
    ap.add_argument(
        "--csv-out",
        default=None,
        help="CSV output path (default: stdout with --csv, else none)",
    )
    ap.add_argument(
        "--full",
        action="store_true",
        help="Print full per-trade table instead of summary only",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()

    summary_path = run_dir / "summary.json"
    if not summary_path.is_file():
        raise SystemExit(f"missing summary: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    trades_csv_path = run_dir / "trades_record.csv"
    trades_jsonl_path = run_dir / "trades.jsonl"
    trades: list[dict[str, Any]] = []
    if trades_csv_path.is_file():
        trades = _read_trades_csv(trades_csv_path)
    elif trades_jsonl_path.is_file():
        trades = list(_read_jsonl(trades_jsonl_path))
    else:
        raise SystemExit("no trades_record.csv or trades.jsonl found")

    iter_path = run_dir / "iterations.jsonl"
    if not iter_path.is_file():
        raise SystemExit(f"missing iterations: {iter_path}")

    stances_by_bar: dict[int, dict[str, Any]] = {}
    for it in _read_jsonl(iter_path):
        bi = it.get("bar_index")
        if bi is None:
            continue
        dec = decision_from_iteration(it)
        dq = it.get("data_quality") if isinstance(it.get("data_quality"), dict) else {}
        stances_by_bar[int(bi)] = {
            "entry_stance_action": str(dec.get("action", "HOLD")),
            "entry_stance_confidence": dec.get("confidence", 0.0),
            "entry_stance": str(dec.get("stance", "")),
            "data_quality_passed": dq.get("passed", True),
        }

    annotated: list[dict[str, Any]] = []
    side_ct: Counter[str] = Counter()
    reason_ct: Counter[str] = Counter()
    pnl_by_reason: defaultdict[str, list[float]] = defaultdict(list)
    hold_bars_all: list[int] = []
    pnl_all: list[float] = []

    for t in trades:
        entry_bar = t.get("entry_bar_index", t.get("entry_bar_index_csv"))
        if entry_bar is not None:
            entry_bar = int(entry_bar)
        elif t.get("entry_bar_index") is not None:
            entry_bar = int(t["entry_bar_index"])
        else:
            entry_bar = 0

        stance = stances_by_bar.get(entry_bar, {})
        side = str(t.get("side", ""))
        reason = str(t.get("exit_reason", ""))
        try:
            pnl = float(t.get("pnl_usd", t.get("pnl", 0)))
        except (ValueError, TypeError):
            pnl = 0.0

        hold_bars = (
            int(t.get("holding_bars", 0)) if str(t.get("holding_bars", "")).isdigit() else None
        )

        row = {
            "trade_id": t.get("trade_id", 0),
            "symbol": t.get("symbol", ""),
            "side": side,
            "entry_price": t.get("entry_price", ""),
            "exit_price": t.get("exit_price", ""),
            "pnl_usd": round(pnl, 2),
            "holding_bars": hold_bars,
            "exit_reason": reason,
            "entry_bar_index": entry_bar,
            "entry_stance_action": stance.get("entry_stance_action", "?"),
            "entry_stance_confidence": stance.get("entry_stance_confidence", 0.0),
            "entry_stance": stance.get("entry_stance", ""),
        }
        annotated.append(row)

        side_ct[side] += 1
        reason_ct[reason] += 1
        pnl_by_reason[reason].append(pnl)
        if hold_bars is not None:
            hold_bars_all.append(hold_bars)
        pnl_all.append(pnl)

    print(f"=== Round-Trip Analysis: {summary.get('run_id')} ===")
    print(f"Total trades: {len(annotated)}")
    print(f"Sides: {dict(side_ct)}")
    print(f"Total PnL (USDT): {sum(pnl_all):.2f}")
    if hold_bars_all:
        avg_hold = sum(hold_bars_all) / len(hold_bars_all)
        print(
            f"Avg holding bars: {avg_hold:.1f}  (max: {max(hold_bars_all)}, min: {min(hold_bars_all)})"
        )
    print("\nExit reason breakdown:")
    for reason, count in reason_ct.most_common():
        reason_pnls = pnl_by_reason[reason]
        avg_pnl = sum(reason_pnls) / len(reason_pnls)
        print(
            f"  {reason:20s}  count={count:4d}  avg_pnl={avg_pnl:+.2f}  total_pnl={sum(reason_pnls):+.2f}"
        )

    wins = [x for x in pnl_all if x > 0]
    losses = [x for x in pnl_all if x <= 0]
    win_rate = len(wins) / max(1, len(pnl_all))
    avg_win = sum(wins) / max(1, len(wins))
    avg_loss = sum(losses) / max(1, len(losses))
    print(f"\nWin rate: {win_rate:.1%} ({len(wins)}W / {len(losses)}L)")
    print(
        f"Avg win: {avg_win:+.2f}  Avg loss: {avg_loss:+.2f}  "
        f"Profit factor: {abs(avg_win / avg_loss) if avg_loss != 0 else float('inf'):.2f}"
    )

    stance_ct: Counter[str] = Counter()
    for r in annotated:
        stance_ct[r["entry_stance_action"]] += 1
    print(f"\nEntry stance actions: {dict(stance_ct)}")

    if args.full:
        print(f"\n{'=' * 100}")
        print(
            f"{'ID':>4} | {'Side':6s} | {'Entry':>10s} | {'Exit':>10s} | "
            f"{'PnL':>8s} | {'Hold':4s} | {'Reason':16s} | {'Stance@Entry':16s} | {'Conf'}"
        )
        print(f"{'-' * 100}")
        for r in annotated:
            side_str = r["side"][:6]
            reason_str = r["exit_reason"][:16]
            stance_str = r["entry_stance_action"][:16]
            print(
                f"{r['trade_id']:>4d} | {side_str:6s} | {r['entry_price']:>10s} | "
                f"{r['exit_price']:>10s} | {r['pnl_usd']:>8.2f} | "
                f"{r['holding_bars'] or '?':>4} | {reason_str:16s} | "
                f"{stance_str:16s} | {r['entry_stance_confidence']:.2f}"
            )

    if args.csv:
        csv_fields = [
            "trade_id",
            "symbol",
            "side",
            "entry_price",
            "exit_price",
            "pnl_usd",
            "holding_bars",
            "exit_reason",
            "entry_bar_index",
            "entry_stance_action",
            "entry_stance_confidence",
            "entry_stance",
        ]
        csv_path = args.csv_out or (run_dir / "trades_with_stance.csv")
        with open(str(csv_path), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=csv_fields)
            w.writeheader()
            w.writerows(annotated)
        print(f"\nWrote stance-annotated CSV: {csv_path}")


if __name__ == "__main__":
    main()
