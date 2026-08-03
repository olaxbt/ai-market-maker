#!/usr/bin/env python3
"""Generate a self-contained HTML backtest report from a run directory."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from backtest.report_html import write_backtest_report_html  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate backtest_report.html from a persisted run.",
        epilog=(
            "Example:\n"
            "  uv run python scripts/generate_backtest_report.py \\\n"
            "    --run-dir .runs/backtests/bt_12345\n"
        ),
    )
    ap.add_argument(
        "--run-dir",
        required=True,
        help="Run directory (.runs/backtests/<run_id>)",
    )
    ap.add_argument(
        "--output",
        default=None,
        help="Output filename (default: backtest_report.html in run dir)",
    )
    args = ap.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    out_name = args.output or "backtest_report.html"
    path = write_backtest_report_html(run_dir, output_name=out_name)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
