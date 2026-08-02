"""Tests for --until period lock helpers and showcase bootstrap sizing."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backtest.bootstrap_showcase import _extra_bars_after_until
from backtest.run_demo import _trailing_bars_locked, _until_end_ms


def _daily_bars(start: datetime, n: int) -> list[list[float]]:
    rows: list[list[float]] = []
    for i in range(n):
        ts = start + timedelta(days=i)
        rows.append([int(ts.timestamp() * 1000), 1.0, 2.0, 0.5, 100.0 + i, 10.0])
    return rows


def test_until_end_ms_is_inclusive_eod_utc():
    ms = _until_end_ms("2026-07-12")
    assert ms is not None
    assert ms == 1_783_900_799_999


def test_until_end_ms_empty():
    assert _until_end_ms(None) is None
    assert _until_end_ms("  ") is None


def test_trailing_bars_locked_without_until_takes_last_n():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = _daily_bars(start, 300)
    out = _trailing_bars_locked(rows, limit=230, until=None, symbol="BTC/USDT")
    assert len(out) == 230
    assert out[0][0] == rows[-230][0]
    assert out[-1][0] == rows[-1][0]


def test_trailing_bars_locked_drops_post_until_bars(capsys):
    start = datetime(2025, 11, 1, tzinfo=timezone.utc)
    rows = _daily_bars(start, 400)
    end_ms = _until_end_ms("2026-07-12")
    assert end_ms is not None
    assert int(rows[-1][0]) > end_ms

    out = _trailing_bars_locked(rows, limit=230, until="2026-07-12", symbol="BTC/USDT")
    assert len(out) == 230
    assert all(int(r[0]) <= end_ms for r in out)
    assert int(out[-1][0]) <= end_ms
    captured = capsys.readouterr()
    assert "window ends 2026-07-12" in captured.err


def test_trailing_bars_locked_raises_when_insufficient():
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = _daily_bars(start, 100)
    with pytest.raises(ValueError, match="only .* bars through --until"):
        _trailing_bars_locked(rows, limit=230, until="2026-07-12", symbol="BTC/USDT")


def test_bootstrap_extra_bars_for_until():
    extra = _extra_bars_after_until("2026-07-12", timeframe="1d")
    assert extra >= 14
    assert _extra_bars_after_until(None, timeframe="1d") == 0
