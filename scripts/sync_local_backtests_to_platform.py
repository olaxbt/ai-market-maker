#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from storage.leadpage_db import database_url, insert_local_backtest_result_if_missing  # noqa: E402


def main() -> None:
    if not database_url():
        raise SystemExit("DATABASE_URL is not set (sync requires Postgres mode).")
    runs_dir = _ROOT / ".runs" / "backtests"
    if not runs_dir.is_dir():
        print("no backtests dir")
        return

    inserted = 0
    scanned = 0
    for p in sorted(runs_dir.iterdir()):
        if not p.is_dir():
            continue
        summary = p / "summary.json"
        if not summary.is_file():
            continue
        scanned += 1
        try:
            obj = json.loads(summary.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(obj, dict) and insert_local_backtest_result_if_missing(summary=obj):
            inserted += 1
    print(f"scanned={scanned} inserted={inserted}")


if __name__ == "__main__":
    main()
