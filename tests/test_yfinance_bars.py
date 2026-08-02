"""Unit tests for Yahoo Finance OHLCV helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from backtest.bars import (
    _yfinance_period_candidates,
    fetch_yfinance_ohlcv_bars,
    interval_sec_to_yfinance_interval,
    normalize_yfinance_symbol,
)


def test_normalize_yfinance_symbol_crypto_and_equity():
    assert normalize_yfinance_symbol("BTC/USDT") == "BTC-USD"
    assert normalize_yfinance_symbol("ETH/USDT:USDT") == "ETH-USD"
    assert normalize_yfinance_symbol("AAPL") == "AAPL"
    assert normalize_yfinance_symbol("US.MSFT") == "MSFT"
    assert normalize_yfinance_symbol("HK.00700") == "0700.HK"


def test_normalize_yfinance_symbol_rejects_empty():
    with pytest.raises(ValueError):
        normalize_yfinance_symbol("  ")


def test_interval_sec_to_yfinance_interval():
    assert interval_sec_to_yfinance_interval(86400) == "1d"
    assert interval_sec_to_yfinance_interval(3600) == "60m"
    assert interval_sec_to_yfinance_interval(300) == "5m"


def test_yfinance_period_candidates_intraday_uses_short_window():
    assert _yfinance_period_candidates("5m", 200)[0] == "60d"
    assert _yfinance_period_candidates("1m", 50)[0] == "7d"
    assert _yfinance_period_candidates("1d", 30)[0] == "6mo"


def test_fetch_yfinance_retries_after_empty_long_period():
    """Regression: 5m + period=2y returns empty from Yahoo; short period must succeed."""
    empty = pd.DataFrame()
    idx = pd.date_range("2026-07-01", periods=5, freq="5min", tz="UTC")
    good = pd.DataFrame(
        {
            "Open": [1.0, 1.1, 1.2, 1.3, 1.4],
            "High": [1.1, 1.2, 1.3, 1.4, 1.5],
            "Low": [0.9, 1.0, 1.1, 1.2, 1.3],
            "Close": [1.05, 1.15, 1.25, 1.35, 1.45],
            "Volume": [10, 11, 12, 13, 14],
        },
        index=idx,
    )
    ticker = MagicMock()
    ticker.history.side_effect = [empty, good]

    with patch("yfinance.Ticker", return_value=ticker):
        rows = fetch_yfinance_ohlcv_bars("AAPL", 5, interval_sec=300)

    assert len(rows) == 5
    assert ticker.history.call_count >= 2
    first_kw = ticker.history.call_args_list[0].kwargs
    assert first_kw.get("period") == "60d"
    assert first_kw.get("interval") == "5m"
