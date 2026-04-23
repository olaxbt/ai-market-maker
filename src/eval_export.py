"""Export run evaluation data for analysis and external benchmarking.

Reads:

- ``.runs/index.jsonl`` — compact per-run ledger (paper/live outcomes)
- ``.runs/backtests/<run_id>/summary.json`` — backtest metrics (when present)

Writes CSV and/or Parquet tables with a ``record_kind`` column (``index`` vs ``backtest``).

Usage::

    uv run python -m eval_export --runs-dir .runs -o exports/evaluation --format both
    uv run aimm-export-eval -o exports/evaluation.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


def read_index_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def read_backtest_summaries(backtests_dir: Path) -> list[dict[str, Any]]:
    if not backtests_dir.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for d in sorted(backtests_dir.iterdir()):
        if not d.is_dir():
            continue
        sp = d / "summary.json"
        if not sp.exists():
            continue
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(data, dict):
            data = dict(data)
            data["_backtest_dir"] = str(d)
            out.append(data)
    return out


def build_evaluation_frame(
    *,
    runs_dir: Path,
    include_backtests: bool = True,
) -> pd.DataFrame:
    """Return one dataframe: index rows and optional flattened backtest summaries."""
    idx_path = runs_dir / "index.jsonl"
    index_rows = read_index_jsonl(idx_path)
    frames: list[pd.DataFrame] = []

    if index_rows:
        df_i = pd.json_normalize(index_rows, sep=".")
        df_i.insert(0, "record_kind", "index")
        frames.append(df_i)

    if include_backtests:
        bt = read_backtest_summaries(runs_dir / "backtests")
        if bt:
            df_b = pd.json_normalize(bt, sep=".")
            df_b.insert(0, "record_kind", "backtest")
            frames.append(df_b)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as e:
        raise SystemExit(
            "Parquet export requires the 'pyarrow' package. Install with:\n"
            "  uv add pyarrow\n"
            "or: pip install pyarrow"
        ) from e
    df.to_parquet(path, index=False)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export .runs/index.jsonl and backtest summaries to CSV/Parquet.",
    )
    p.add_argument(
        "--runs-dir",
        type=Path,
        default=Path(".runs"),
        help="Directory containing index.jsonl and backtests/ (default: .runs)",
    )
    p.add_argument(
        "--no-backtests",
        action="store_true",
        help="Only export index.jsonl; skip .runs/backtests/*/summary.json",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("exports/evaluation"),
        help="Output base path (adds .csv / .parquet) or a path ending in .csv/.parquet",
    )
    p.add_argument(
        "-f",
        "--format",
        choices=("csv", "parquet", "both"),
        default="csv",
        help="Output format (default: csv). Parquet requires pyarrow.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    df = build_evaluation_frame(
        runs_dir=args.runs_dir,
        include_backtests=not args.no_backtests,
    )
    if df.empty:
        print(
            f"No data found under {args.runs_dir} "
            "(missing or empty index.jsonl and no backtest summaries).",
            file=sys.stderr,
        )
        return 1

    out = args.output
    suf = out.suffix.lower()
    written: list[Path] = []

    if suf == ".csv":
        out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out, index=False)
        written = [out]
    elif suf == ".parquet":
        out.parent.mkdir(parents=True, exist_ok=True)
        _write_parquet(df, out)
        written = [out]
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        if args.format in ("csv", "both"):
            p = out.with_suffix(".csv")
            df.to_csv(p, index=False)
            written.append(p)
        if args.format in ("parquet", "both"):
            p = out.with_suffix(".parquet")
            _write_parquet(df, p)
            written.append(p)

    for path in written:
        print(path)
    print(f"rows={len(df)} cols={len(df.columns)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
