"""Trade / equity JSONL persistence (one record per line + legacy reader)."""

from __future__ import annotations

import json
from pathlib import Path

from backtest.trade_book import read_jsonl_dict_records, write_jsonl_records


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    rows = [{"a": 1}, {"b": 2}]
    write_jsonl_records(path, rows)
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert read_jsonl_dict_records(path) == rows


def test_read_legacy_single_line_array(tmp_path: Path) -> None:
    path = tmp_path / "legacy.jsonl"
    path.write_text(json.dumps([{"side": "buy"}, {"side": "sell"}]) + "\n", encoding="utf-8")
    assert read_jsonl_dict_records(path) == [{"side": "buy"}, {"side": "sell"}]


def test_read_jsonl_respects_limit(tmp_path: Path) -> None:
    path = tmp_path / "many.jsonl"
    write_jsonl_records(path, [{"i": i} for i in range(10)])
    assert len(read_jsonl_dict_records(path, limit=3)) == 3
