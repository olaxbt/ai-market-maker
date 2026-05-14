from __future__ import annotations

import pytest

import adapters.futu as futu_mod


def test_interval_sec_to_futu_interval_monthly_token() -> None:
    from backtest.bars import interval_sec_to_futu_interval

    assert interval_sec_to_futu_interval(2_592_000) == "1mon"
    assert interval_sec_to_futu_interval(86400) == "1d"


def test_fetch_futu_ohlcv_bars_uses_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubAdapter:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def get_history_kline(self, *, symbol: str, interval: str, limit: int):
            assert "HK.00700" in symbol or symbol.startswith("HK.")
            assert interval == "1d"
            assert limit == 3
            return [
                [1.0, 10.0, 11.0, 9.0, 10.5, 100.0],
                [2.0, 10.5, 11.5, 10.0, 11.0, 110.0],
                [3.0, 11.0, 12.0, 10.5, 11.5, 120.0],
            ]

        def close(self) -> None:
            pass

    monkeypatch.setattr(futu_mod, "FutuAdapter", StubAdapter)

    from backtest.bars import fetch_futu_ohlcv_bars

    rows = fetch_futu_ohlcv_bars("HK.00700", 3, interval_sec=86_400)
    assert len(rows) == 3
    assert rows[0][4] == 10.5
