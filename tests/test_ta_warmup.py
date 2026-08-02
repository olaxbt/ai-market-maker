"""Tests for TA warmup prefetch helpers."""

from __future__ import annotations

from backtest.ta_warmup import (
    resolve_ta_warmup_bars,
    split_warmup_index,
    total_fetch_bars,
    warmup_fetch_since_ms,
)


def test_resolve_zero_warmup():
    assert resolve_ta_warmup_bars(override=0) == 0


def test_total_fetch_bars_adds_warmup():
    fetch, warmup = total_fetch_bars(eval_steps=90, warmup_bars=50)
    assert fetch == 140
    assert warmup == 50


def test_total_fetch_bars_minimum_eval():
    fetch, warmup = total_fetch_bars(eval_steps=1, warmup_bars=10)
    assert fetch == 12  # eval clamped to 2
    assert warmup == 10


def test_warmup_fetch_since_ms_extends_before_eval():
    day_ms = 86_400_000
    eval_since = 1_700_000_000_000
    fetch_since, w = warmup_fetch_since_ms(
        eval_since_ms=eval_since, interval_sec=86_400, warmup_bars=50
    )
    assert w == 50
    assert fetch_since == eval_since - 50 * day_ms


def test_split_warmup_index_finds_eval_start():
    day_ms = 86_400_000
    eval_since = 1_700_000_000_000 + 5 * day_ms
    bars = [[1_700_000_000_000 + i * day_ms, 1.0, 1.0, 1.0, 1.0, 1.0] for i in range(10)]
    assert split_warmup_index(bars, eval_since_ms=eval_since) == 5
