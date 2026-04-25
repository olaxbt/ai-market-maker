"""Tests for data loader registry and individual loaders."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pandas as pd
import pytest

from backtest.loaders.base import NoAvailableSourceError, validate_date_range
from backtest.loaders.registry import (
    FALLBACK_CHAINS,
    LOADER_REGISTRY,
    register,
    resolve_loader,
)


class TestValidateDateRange:
    def test_valid_range(self):
        validate_date_range("2024-01-01", "2024-01-31")

    def test_invalid_order_raises(self):
        with pytest.raises(ValueError, match="start_date"):
            validate_date_range("2024-02-01", "2024-01-01")

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Invalid date format"):
            validate_date_range("not-a-date", "2024-01-31")

    def test_same_date_is_valid(self):
        validate_date_range("2024-01-01", "2024-01-01")


class TestRegistry:
    def test_register_decorator(self):
        @register
        class _TestLoader:
            name = "_unittest_test"
            markets = {"crypto"}
            requires_auth = False

            def fetch(self, codes, start, end, **kw):
                return {}

        assert "_unittest_test" in LOADER_REGISTRY
        assert LOADER_REGISTRY["_unittest_test"] is _TestLoader

    def test_registry_has_all_loaders(self):
        assert "ccxt" in LOADER_REGISTRY
        assert "futu" in LOADER_REGISTRY
        assert "yfinance" in LOADER_REGISTRY

    def test_fallback_chains_defined(self):
        assert "crypto" in FALLBACK_CHAINS
        assert "hk_equity" in FALLBACK_CHAINS
        assert "a_share" in FALLBACK_CHAINS
        assert "us_equity" in FALLBACK_CHAINS

    def test_resolve_returns_first_in_chain(self):
        loader = resolve_loader("crypto")
        assert loader.name == "ccxt"

    def test_resolve_unknown_raises(self):
        with pytest.raises(NoAvailableSourceError):
            resolve_loader("nonexistent_market_xyz")

    def test_resolve_hk_equity_returns_futu(self):
        loader = resolve_loader("hk_equity")
        assert loader.name == "futu"

    def test_resolve_us_returns_yfinance(self):
        loader = resolve_loader("us_equity")
        assert loader.name == "yfinance"


class TestFutuSymbol:
    def test_hk(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("700.HK") == "HK.00700"

    def test_hk_short_padded(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("5.HK") == "HK.00005"

    def test_sz(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("000001.SZ") == "SZ.000001"

    def test_sh(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("600519.SH") == "SH.600519"

    def test_case_insensitive(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("700.hk") == "HK.00700"


class TestFutuKtype:
    @pytest.fixture(autouse=True)
    def mock_futu(self, monkeypatch):
        futu_mock = MagicMock()
        futu_mock.KLType.K_DAY = "K_DAY"
        futu_mock.KLType.K_60M = "K_60M"
        futu_mock.KLType.K_30M = "K_30M"
        futu_mock.KLType.K_WEEK = "K_WEEK"
        futu_mock.KLType.K_MON = "K_MON"
        monkeypatch.setitem(sys.modules, "futu", futu_mock)

    def test_daily(self):
        from backtest.loaders.futu_loader import _to_futu_ktype

        assert _to_futu_ktype("1D") == "K_DAY"

    def test_hourly(self):
        from backtest.loaders.futu_loader import _to_futu_ktype

        assert _to_futu_ktype("1H") == "K_60M"

    def test_four_hour_falls_back_to_day(self):
        from backtest.loaders.futu_loader import _to_futu_ktype

        assert _to_futu_ktype("4H") == "K_DAY"

    def test_unknown_defaults_to_day(self):
        from backtest.loaders.futu_loader import _to_futu_ktype

        assert _to_futu_ktype("unknown") == "K_DAY"


class TestNormalizeFrame:
    def test_empty_input(self):
        from backtest.loaders.futu_loader import _normalize_frame

        result = _normalize_frame(pd.DataFrame())
        assert result.empty
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_happy_path(self):
        from backtest.loaders.futu_loader import _normalize_frame

        df = pd.DataFrame(
            {
                "code": ["HK.00700", "HK.00700"],
                "time_key": ["2024-01-02 00:00:00", "2024-01-03 00:00:00"],
                "open": [350.0, 355.0],
                "high": [360.0, 358.0],
                "low": [345.0, 352.0],
                "close": [355.0, 356.0],
                "volume": [1_000_000, 900_000],
                "turnover": [350_000_000.0, 320_000_000.0],
            }
        )
        result = _normalize_frame(df)
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]
        assert result.index.name == "trade_date"
        assert len(result) == 2
