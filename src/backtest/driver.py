from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from config.run_mode import RunMode
from flow_log import FlowEventRepo, set_flow_repo
from main import build_workflow
from schemas.state import initial_hedge_fund_state

from .export_run import export_run_bundle


def _load_market_data(path: Path | None) -> Dict[str, Any]:
    if path is None:
        return {}
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline backtest/replay driver (deterministic).")
    parser.add_argument("--ticker", type=str, default="BTC/USDT")
    parser.add_argument(
        "--market-data",
        type=str,
        default=None,
        help="Path to JSON market_data dict to inject into state (offline backtest).",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default="backtest-run",
        help="Run id used for .runs/<run_id>.events.jsonl.",
    )
    parser.add_argument(
        "--export-bundle",
        action="store_true",
        help="Also export a replay bundle (.runs/bundles/<run_id>/...).",
    )
    args = parser.parse_args()

    runs_dir = Path(".runs")
    runs_dir.mkdir(parents=True, exist_ok=True)
    (runs_dir / "latest_run.txt").write_text(args.run_id)
    log_path = runs_dir / f"{args.run_id}.events.jsonl"
    if log_path.exists():
        log_path.unlink()

    market_data = _load_market_data(Path(args.market_data) if args.market_data else None)
    state = initial_hedge_fund_state(run_mode=RunMode.BACKTEST.value, ticker=args.ticker)
    state["market_data"] = market_data

    repo = FlowEventRepo(run_id=args.run_id, log_path=log_path)
    set_flow_repo(repo)
    try:
        app = build_workflow().compile()
        app.invoke(state)
    finally:
        set_flow_repo(None)

    if args.export_bundle:
        export_run_bundle(run_id=args.run_id, out_dir=runs_dir / "bundles")


if __name__ == "__main__":
    main()
