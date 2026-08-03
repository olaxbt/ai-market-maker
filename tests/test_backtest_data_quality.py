"""Tests for OHLCV data-integrity validation."""

from __future__ import annotations

from backtest.data_quality import validate_ohlcv_window


class TestValidateOhlcvWindow:
    def test_empty_window(self):
        r = validate_ohlcv_window(
            [], symbol="BTC/USDT", expected_ticker="BTC/USDT", interval_sec=86400
        )
        assert not r.passed
        assert len(r.warnings) >= 1
        assert "empty" in r.warnings[0].lower()

    def test_good_window(self):
        bars = [
            [1700000000000 + i * 86400000, 100.0, 101.0, 99.0, 100.5, 1000.0] for i in range(10)
        ]
        r = validate_ohlcv_window(
            bars, symbol="BTC/USDT", expected_ticker="BTC/USDT", interval_sec=86400
        )
        assert r.passed
        assert r.checks["monotonic_ts"]
        assert r.checks["gap_ok"]
        assert r.checks["min_bars"]

    def test_non_monotonic_timestamps(self):
        bars = [
            [1700000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
            [1699999999000, 101.0, 102.0, 100.0, 101.5, 1100.0],  # earlier ts
            [1700000008000, 102.0, 103.0, 101.0, 102.5, 1200.0],
        ]
        r = validate_ohlcv_window(
            bars, symbol="BTC/USDT", expected_ticker="BTC/USDT", interval_sec=3600
        )
        assert not r.passed
        assert not r.checks["monotonic_ts"]

    def test_gap_detection(self):
        bars = [
            [1700000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
            [1700000864000, 101.0, 102.0, 100.0, 101.5, 1100.0],  # ~14.4min, should pass 1h
        ]
        r = validate_ohlcv_window(
            bars, symbol="ETH/USDT", expected_ticker="ETH/USDT", interval_sec=3600
        )
        assert r.passed
        assert r.checks["gap_ok"]

    def test_gap_too_large(self):
        bars = [
            [1700000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
            [1700200000000, 101.0, 102.0, 100.0, 101.5, 1100.0],  # ~55.6h later, >> 1.5*1d
        ]
        r = validate_ohlcv_window(
            bars, symbol="BTC/USDT", expected_ticker="BTC/USDT", interval_sec=86400
        )
        assert not r.passed
        assert not r.checks["gap_ok"]

    def test_min_bars_check(self):
        bars = [
            [1700000000000, 100.0, 101.0, 99.0, 100.5, 1000.0],
        ]
        r = validate_ohlcv_window(
            bars, symbol="BTC/USDT", expected_ticker="BTC/USDT", interval_sec=86400, min_bars=5
        )
        assert not r.passed
        assert not r.checks["min_bars"]

    def test_ticker_mismatch(self):
        bars = [[1700000000000 + i * 86400000, 100.0, 101.0, 99.0, 100.5, 1000.0] for i in range(5)]
        r = validate_ohlcv_window(
            bars, symbol="SOL/USDT", expected_ticker="BTC/USDT", interval_sec=86400
        )
        assert not r.passed
        assert not r.checks["ticker_match"]
