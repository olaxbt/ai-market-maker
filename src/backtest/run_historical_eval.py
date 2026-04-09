"""Run anchored multi-window backtests and write ``evaluation_report.json`` + ``.md``.

**Daily suite (deterministic graph, no LLM by default)** — reproducible windows, full bar count::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite daily

**Monthly + LLM** (fewer steps; set provider keys in ``.env``)::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite llm_monthly --llm

Artifacts: ``.runs/evaluations/<eval_id>/evaluation_report.{json,md}`` plus per-window backtest dirs under ``.runs/backtests/``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from backtest.historical_eval import (
    DEFAULT_DAILY_WINDOWS,
    LLM_MONTHLY_WINDOWS,
    report_to_markdown,
    run_suite,
)
from config.app_settings import load_app_settings


def main() -> None:
    # Always let `.env` win over inherited shell env (including empty values).
    load_dotenv(override=True)
    ticker_def = load_app_settings().market.default_ticker
    parser = argparse.ArgumentParser(
        description="Anchored historical multi-window backtest report."
    )
    parser.add_argument(
        "--suite",
        choices=("daily", "llm_monthly"),
        default="daily",
        help="daily: six-month 1d windows; llm_monthly: yearly 1M windows (fewer LLM steps).",
    )
    parser.add_argument(
        "--llm", action="store_true", help="Enable Tier-2 LLM arbitrator (API keys required)."
    )
    parser.add_argument("--ticker", default=ticker_def)
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--initial-cash", type=float, default=10_000.0)
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(".runs"),
        help="Root for backtests/ and evaluations/ (default: .runs).",
    )
    parser.add_argument(
        "--max-windows",
        type=int,
        default=None,
        help="If set, only run the first N windows (smoke / faster iteration).",
    )
    args = parser.parse_args()

    use_llm = bool(args.llm) or args.suite == "llm_monthly"
    if use_llm:
        os.environ["AI_MARKET_MAKER_USE_LLM"] = "1"
    cap_raw = (os.getenv("AIMM_BACKTEST_LLM_MAX_STEPS") or "120").strip()
    try:
        llm_max = max(2, int(cap_raw, 10))
    except ValueError:
        llm_max = 120

    windows = DEFAULT_DAILY_WINDOWS if args.suite == "daily" else LLM_MONTHLY_WINDOWS
    if args.max_windows is not None:
        windows = tuple(windows[: max(1, int(args.max_windows))])
    if use_llm and args.suite == "daily":
        print(
            f"[eval] LLM on daily suite: up to {llm_max} bars per window (cap); "
            f"prefer --suite llm_monthly for multi-year LLM without heavy truncation.",
            file=sys.stderr,
        )

    print(
        f"[eval] suite={args.suite} windows={len(windows)} ticker={args.ticker} llm={use_llm}",
        file=sys.stderr,
    )
    report = run_suite(
        windows,
        ticker=str(args.ticker),
        exchange=str(args.exchange),
        initial_cash=float(args.initial_cash),
        runs_dir=args.runs_dir,
        use_llm=use_llm,
        llm_max_steps=llm_max,
    )
    rp = Path(report["report_path"])
    rp.with_suffix(".md").write_text(report_to_markdown(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "windows"}, indent=2))
    print(json.dumps(report["aggregate"], indent=2))
    print(f"\nFull report: {rp}", file=sys.stderr)
    print(f"Markdown:    {rp.with_suffix('.md')}", file=sys.stderr)


if __name__ == "__main__":
    main()
