"""Append-only trade / equity journal for backtests (JSONL)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


def write_jsonl_records(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    """Write one JSON object per line (true JSONL)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(dict(row), default=str) + "\n")


def _expand_jsonl_value(val: Any) -> list[dict[str, Any]]:
    if isinstance(val, dict):
        return [val]
    if isinstance(val, list):
        return [x for x in val if isinstance(x, dict)]
    return []


def read_jsonl_dict_records(path: Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    """Read ``.jsonl`` rows as dicts.

    Supports **legacy** files where a single line held a JSON array of records (older engine bug).
    """
    out: list[dict[str, Any]] = []
    if not path.is_file():
        return out
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            val = json.loads(line)
            for d in _expand_jsonl_value(val):
                out.append(d)
                if limit is not None and len(out) >= limit:
                    return out
    return out
