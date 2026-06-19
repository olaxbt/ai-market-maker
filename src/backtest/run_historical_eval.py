"""Run anchored multi-window backtests and write ``evaluation_report.json`` + ``.md``.

**Daily suite (deterministic graph, no LLM by default)** — reproducible windows, full bar count::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite daily

**Monthly + LLM** (fewer steps; set provider keys in ``.env``)::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite llm_monthly --llm

**Deploy parity (uses arbitrator mode + weights from ``deploy.active.json``):** ::

    NEXUS_DISABLE=1 uv run python -m backtest.run_historical_eval --suite llm_monthly --llm --deploy

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
        "--llm",
        action="store_true",
        help="Enable LLM arbitrator. Uses ``agent_llm`` mode (per-agent LLM).",
    )
    parser.add_argument(
        "--mode",
        default=None,
        choices=("agent_llm", "weighted_convergence"),
        help="Explicitly set arbitrator mode (overrides deploy config).",
    )
    parser.add_argument(
        "--deploy",
        nargs="?",
        const="config/deploy.active.json",
        default=None,
        metavar="PATH",
        help="Load profile weights + arbitrator mode from deploy config (default: config/deploy.active.json).",
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
    parser.add_argument(
        "--tp-sl-pct",
        type=float,
        default=None,
        metavar="PCT",
        help="Set symmetric take-profit / stop-loss at ±PCT%% from entry (overrides deploy config).",
    )
    parser.add_argument(
        "--forward-validate",
        action="store_true",
        help="Run IS/OOS split for each window and report forward validation score.",
    )
    parser.add_argument(
        "--forward-oos-bars",
        type=int,
        default=30,
        metavar="N",
        help="Number of OOS bars for forward validation (default: 30).",
    )
    parser.add_argument(
        "--quality",
        action="store_true",
        help="Apply quality-optimized defaults: implies ``--tp-sl-pct 5`` + forward validation.",
    )
    args = parser.parse_args()

    if args.quality:
        if args.tp_sl_pct is None or args.tp_sl_pct <= 0:
            args.tp_sl_pct = 5.0
        if not args.forward_validate:
            args.forward_validate = True
        print(
            "[quality] preset: --tp-sl-pct 5 --forward-validate --forward-oos-bars "
            f"{args.forward_oos_bars}",
            file=sys.stderr,
        )

    from backtest.config import resolve_backtest_config, set_env_from_config

    bt_cfg = resolve_backtest_config(
        deploy_path=args.deploy,
        cli_arbitrator_mode=args.mode,
        cli_tp_sl_pct=args.tp_sl_pct,
    )

    if args.llm and args.mode is None:
        bt_cfg["arbitrator_mode"] = "agent_llm"
        bt_cfg["use_llm"] = True

    set_env_from_config(bt_cfg)

    use_llm = bt_cfg["use_llm"]

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
        f"[eval] suite={args.suite} windows={len(windows)} ticker={args.ticker} "
        f"config={bt_cfg['source_description']}",
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
        deploy_profile_weights=bt_cfg.get("profile_weights"),
        deploy_profile_id=bt_cfg.get("profile_id"),
        deploy_arbitrator_mode=bt_cfg.get("arbitrator_mode"),
        take_profit_pct=bt_cfg.get("take_profit_pct", 0.0),
        stop_loss_pct=bt_cfg.get("stop_loss_pct", 0.0),
        max_hold_bars=bt_cfg.get("max_hold_bars", 0),
        forward_validate=bool(args.forward_validate),
        forward_oos_bars=int(args.forward_oos_bars),
        deploy_config=bt_cfg,
    )
    report["resolved_config"] = {
        "arbitrator_mode": bt_cfg["arbitrator_mode"],
        "deploy_loaded": bt_cfg["deploy_loaded"],
        "deploy_path": bt_cfg["deploy_path"],
        "profile_id": bt_cfg["profile_id"],
        "profile_weights": bt_cfg.get("profile_weights", {}),
        "take_profit_pct": bt_cfg["take_profit_pct"],
        "stop_loss_pct": bt_cfg["stop_loss_pct"],
        "leverage": bt_cfg["leverage"],
    }

    rp = Path(report["report_path"])
    rp.with_suffix(".md").write_text(report_to_markdown(report), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "windows"}, indent=2))
    print(json.dumps(report["aggregate"], indent=2))
    print(f"\nFull report: {rp}", file=sys.stderr)
    print(f"Markdown:    {rp.with_suffix('.md')}", file=sys.stderr)


if __name__ == "__main__":
    main()
