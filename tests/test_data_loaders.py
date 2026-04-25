"""Tests for Loader Registry and CCXT loader."""

from __future__ import annotations

import pandas as pd
import pytest

from backtest.loaders.base import DataLoaderProtocol, NoAvailableSourceError, validate_date_range
from backtest.loaders.registry import (
    FALLBACK_CHAINS,
    LOADER_REGISTRY,
    _ensure_registered,
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


class TestProtocol:
    def test_protocol_runtime_checkable(self):
        class FakeLoader:
            name = "test"
            markets = {"crypto"}
            requires_auth = False

            def is_available(self):
                return True

            def fetch(self, codes, start, end, *, interval="1D", fields=None):
                return {}

        assert isinstance(FakeLoader(), DataLoaderProtocol)


class TestRegistry:
    def test_register_decorator(self):
        @register
        class _TestLoader:
            name = "_unittest_test"
            markets = {"crypto"}
            requires_auth = False

            def is_available(self):
                return False

            def fetch(self, codes, start, end, *, interval="1D", fields=None):
                return {}

        assert "_unittest_test" in LOADER_REGISTRY
        assert LOADER_REGISTRY["_unittest_test"] is _TestLoader

    def test_registry_has_ccxt(self):
        _ensure_registered()
        assert "ccxt" in LOADER_REGISTRY

    def test_fallback_chains_defined(self):
        assert "crypto" in FALLBACK_CHAINS
        assert "hk_equity" in FALLBACK_CHAINS

    def test_resolve_crypto_tries_ccxt(self):
        _ensure_registered()
        loader = resolve_loader("crypto")
        assert loader.name == "ccxt"

    def test_resolve_unknown_raises(self):
        with pytest.raises(NoAvailableSourceError):
            resolve_loader("nonexistent_market_xyz")


class TestCCXTLoader:
    def test_imports(self):
        from backtest.loaders.ccxt_loader import CCXTLoader

        assert CCXTLoader.name == "ccxt"
        assert "crypto" in CCXTLoader.markets

    def test_is_available_returns_bool(self):
        from backtest.loaders.ccxt_loader import CCXTLoader

        result = CCXTLoader().is_available()
        assert isinstance(result, bool)


class TestFutuLoader:
    def test_imports(self):
        from backtest.loaders.futu_loader import (
            FutuLoader,
        )

        assert FutuLoader.name == "futu"
        assert "hk_equity" in FutuLoader.markets

    def test_symbol_hk(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("700.HK") == "HK.00700"

    def test_symbol_hk_short_padded(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("5.HK") == "HK.00005"

    def test_symbol_sz(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("000001.SZ") == "SZ.000001"

    def test_symbol_sh(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("600519.SH") == "SH.600519"

    def test_symbol_case_insensitive(self):
        from backtest.loaders.futu_loader import _to_futu_symbol

        assert _to_futu_symbol("700.hk") == "HK.00700"

    def test_ktype_daily(self):
        import sys
        from unittest.mock import MagicMock

        from backtest.loaders.futu_loader import _to_futu_ktype

        futu_stub = MagicMock()
        futu_stub.KLType.K_DAY = "K_DAY"
        futu_stub.KLType.K_60M = "K_60M"
        futu_stub.KLType.K_240M = "K_240M"
        futu_stub.KLType.K_WEEK = "K_WEEK"
        futu_stub.KLType.K_MON = "K_MON"
        sys.modules["futu"] = futu_stub

        assert _to_futu_ktype("1D") == "K_DAY"
        assert _to_futu_ktype("1H") == "K_60M"
        assert _to_futu_ktype("unknown") == "K_DAY"

    def test_normalize_frame_empty(self):
        from backtest.loaders.futu_loader import _normalize_frame

        result = _normalize_frame(pd.DataFrame())
        assert result.empty
        assert list(result.columns) == ["open", "high", "low", "close", "volume"]

    def test_normalize_frame_columns(self):
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

    def test_normalize_frame_drops_nan_ohlc(self):
        from backtest.loaders.futu_loader import _normalize_frame

        df = pd.DataFrame(
            {
                "code": ["HK.00700", "HK.00700"],
                "time_key": ["2024-01-02 00:00:00", "2024-01-03 00:00:00"],
                "open": [350.0, None],
                "high": [360.0, None],
                "low": [345.0, None],
                "close": [355.0, None],
                "volume": [1_000_000, 900_000],
                "turnover": [350_000_000.0, 320_000_000.0],
            }
        )
        result = _normalize_frame(df)
        assert len(result) == 1
