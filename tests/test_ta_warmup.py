"""Tests for TA warmup prefetch helpers."""

from __future__ import annotations

from backtest.ta_warmup import resolve_ta_warmup_bars, total_fetch_bars


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
