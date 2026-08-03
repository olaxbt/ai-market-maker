#!/usr/bin/env python3
"""Paper trading loop with scan-phase status for the Live desk."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = REPO_ROOT / ".runs" / "paper_engine.status.json"


def _merge_status(**fields: Any) -> None:
    """Patch paper_engine.status.json without dropping fields set by the API / main.py."""
    try:
        STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
        st: dict[str, Any] = {}
        if STATUS_PATH.is_file():
            raw = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                st = raw
        st.update(fields)
        st["updated_at"] = int(time.time())
        STATUS_PATH.write_text(json.dumps(st, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[paper-loop] status write failed: {exc}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Live paper agent loop")
    parser.add_argument("--ticker", default=os.getenv("TICKER", "BTC/USDT"))
    parser.add_argument(
        "--interval-sec",
        type=int,
        default=int(os.getenv("STRATEGY_INTERVAL_SEC", "900") or "900"),
    )
    args = parser.parse_args()
    interval = max(300, int(args.interval_sec))
    ticker = str(args.ticker).strip() or "BTC/USDT"

    env = os.environ.copy()
    env["MODE"] = "paper"
    env["TICKER"] = ticker
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")

    main_py = REPO_ROOT / "src" / "main.py"
    iteration = 0
    while True:
        iteration += 1
        now = int(time.time())
        _merge_status(
            ticker=ticker,
            interval_sec=interval,
            phase="scanning",
            scan_iteration=iteration,
            last_scan_started_at=now,
            next_scan_at=None,
        )
        print(f"[paper-loop] invoke ticker={ticker} iteration={iteration}", flush=True)
        proc = subprocess.run(
            [sys.executable, str(main_py), "--mode", "paper", "--ticker", ticker],
            cwd=str(REPO_ROOT),
            env=env,
            check=False,
        )
        finished = int(time.time())
        next_at = finished + interval
        if proc.returncode != 0:
            print(f"[paper-loop] iteration exit={proc.returncode}", flush=True)
        _merge_status(
            ticker=ticker,
            interval_sec=interval,
            phase="waiting",
            scan_iteration=iteration,
            last_scan_finished_at=finished,
            last_scan_exit_code=int(proc.returncode),
            next_scan_at=next_at,
        )
        print(f"[paper-loop] sleeping {interval}s (next_scan_at={next_at})", flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    main()
