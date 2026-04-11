"""Tests for TA-Lib indicator bundle."""

from __future__ import annotations

import math

import pytest

pytest.importorskip("talib")

from tools.technical_indicators import calculate_technical_indicators, indicator_keys


def _synthetic_ohlcv(n: int = 120) -> tuple[list[float], list[float], list[float], list[float]]:
    base = [100.0 + i * 0.1 + (0.3 if i % 2 == 0 else -0.2) for i in range(n)]
    high = [x * 1.005 for x in base]
    low = [x * 0.995 for x in base]
    vol = [1_000_000.0 + i * 100 for i in range(n)]
    return base, high, low, vol


def test_indicator_keys_count():
    keys = indicator_keys()
    assert len(keys) >= 10
    assert "rsi" in keys
    assert "macd_hist" in keys
    assert "atr" in keys


def test_close_only_returns_core_indicators():
    close, *_ = _synthetic_ohlcv(80)
    out = calculate_technical_indicators(close, period=14)
    assert not math.isnan(out["rsi"])
    assert not math.isnan(out["sma"])
    assert not math.isnan(out["ema"])
    assert not math.isnan(out["bb_upper"])
    assert "macd_hist" in out
    # HLC-dependent left NaN without high/low
    assert math.isnan(out["atr"])
    assert math.isnan(out["adx"])


def test_full_ohlcv_populates_hlc_volume_indicators():
    close, high, low, vol = _synthetic_ohlcv(120)
    out = calculate_technical_indicators(close, period=14, high=high, low=low, volume=vol)
    assert not math.isnan(out["rsi"])
    assert not math.isnan(out["atr"])
    assert not math.isnan(out["stoch_k"])
    assert not math.isnan(out["adx"])
    assert not math.isnan(out["cci"])
    assert not math.isnan(out["willr"])
    assert not math.isnan(out["obv"])
    assert not math.isnan(out["mfi"])


def test_short_series_returns_defaults():
    out = calculate_technical_indicators([100.0, 101.0], period=14)
    assert out["rsi"] == 50.0
    assert math.isnan(out["macd"])
