"""OHLCV CSV cache helpers (no network unless mocked)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backtest.ohlcv_csv_cache import (
    ensure_bars_cached,
    load_bars_csv_only,
    load_ohlcv_csv,
    ohlcv_cache_path,
    save_ohlcv_csv,
)


def _fake_bars(
    n: int, *, start_ts_ms: int = 1_700_000_000_000, interval_sec: int = 86_400
) -> list[list[float]]:
    """Deterministic OHLCV bars for cache tests (no network)."""
    step = int(interval_sec) * 1000
    out: list[list[float]] = []
    px = 100.0
    for i in range(int(n)):
        ts = float(start_ts_ms + i * step)
        o = px
        c = px * (1.0 + 0.001 * ((i % 7) - 3) / 3.0)
        h = max(o, c) * 1.001
        lo = min(o, c) * 0.999
        v = 10.0 + i
        out.append([ts, float(o), float(h), float(lo), float(c), float(v)])
        px = c
    return out


def test_save_load_roundtrip(tmp_path: Path) -> None:
    bars = _fake_bars(10, interval_sec=86_400)
    p = tmp_path / "t.csv"
    save_ohlcv_csv(p, bars)
    got = load_ohlcv_csv(p)
    assert len(got) == 10
    assert got[0][0] == bars[0][0]
    assert got[-1][4] == bars[-1][4]


def test_load_bars_csv_only_takes_last_n(tmp_path: Path) -> None:
    bars = _fake_bars(20, interval_sec=86_400)
    p = ohlcv_cache_path(tmp_path, "BTC/USDT", "1d")
    save_ohlcv_csv(p, bars)
    tail = load_bars_csv_only("BTC/USDT", 5, timeframe="1d", cache_dir=tmp_path)
    assert len(tail) == 5
    assert tail[-1][0] == bars[-1][0]


def test_load_bars_csv_only_too_short_raises(tmp_path: Path) -> None:
    bars = _fake_bars(3, interval_sec=86_400)
    p = ohlcv_cache_path(tmp_path, "ETH/USDT", "1d")
    save_ohlcv_csv(p, bars)
    with pytest.raises(ValueError, match="prefetch"):
        load_bars_csv_only("ETH/USDT", 10, timeframe="1d", cache_dir=tmp_path)


def test_ensure_bars_cached_uses_fetch_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = _fake_bars(8, interval_sec=3600)

    def _fake_fetch(
        symbol: str,
        limit: int,
        *,
        timeframe: str = "1d",
        exchange_id: str = "binance",
    ) -> list[list[float]]:
        return fake[-limit:]

    monkeypatch.setattr(
        "backtest.ohlcv_csv_cache.fetch_ccxt_ohlcv_bars",
        _fake_fetch,
    )
    got = ensure_bars_cached(
        "BTC/USDT",
        6,
        timeframe="1h",
        exchange_id="binance",
        cache_dir=tmp_path,
        refresh=False,
    )
    assert len(got) == 6
    p = ohlcv_cache_path(tmp_path, "BTC/USDT", "1h")
    assert p.is_file()
    got2 = load_ohlcv_csv(p)
    assert len(got2) == 6


def test_ensure_bars_cached_hit_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bars = _fake_bars(12, interval_sec=86_400)
    p = ohlcv_cache_path(tmp_path, "SOL/USDT", "1d")
    save_ohlcv_csv(p, bars)

    def _boom(*_a, **_k):
        raise AssertionError("fetch should not run on cache hit")

    monkeypatch.setattr(
        "backtest.ohlcv_csv_cache.fetch_ccxt_ohlcv_bars",
        _boom,
    )
    got = ensure_bars_cached(
        "SOL/USDT",
        10,
        timeframe="1d",
        exchange_id="binance",
        cache_dir=tmp_path,
        refresh=False,
    )
    assert len(got) == 10
