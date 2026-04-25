"""Futu OpenAPI-backed loader for HK and China A-share OHLCV data."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import futu
import pandas as pd

from .base import validate_date_range

_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
_INTERVAL_MAP: dict[str, str] = {
    "1D": "K_DAY",
    "1H": "K_60M",
    "4H": "K_DAY",
    "1W": "K_WEEK",
    "1M": "K_MON",
}


def _to_futu_symbol(code: str) -> str:
    upper = code.strip().upper()
    if upper.endswith(".HK"):
        return f"HK.{upper[:-3].zfill(5)}"
    if upper.endswith(".SZ"):
        return f"SZ.{upper[:-3].zfill(6)}"
    if upper.endswith(".SH"):
        return f"SH.{upper[:-3].zfill(6)}"
    return upper


def _to_futu_ktype(interval: str) -> str:
    return getattr(futu.KLType, _INTERVAL_MAP.get(interval.strip(), "K_DAY"))


def _normalize_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=_OHLCV_COLUMNS)
    result = df.copy()
    result.index = pd.to_datetime(result["time_key"])
    result.index.name = "trade_date"
    result = result[_OHLCV_COLUMNS].copy()
    result = result.apply(pd.to_numeric, errors="coerce")
    result["volume"] = result["volume"].fillna(0.0)
    result = result.dropna(subset=["open", "high", "low", "close"])
    return result.sort_index()


class FutuLoader:
    """Fetch HK and China A-share bars from Futu OpenAPI.

    Requires FutuOpenD running locally (https://www.futunn.com/download/openAPI).
    """

    name = "futu"
    markets = {"hk_equity", "a_share", "us_equity"}
    requires_auth = True

    def __init__(self) -> None:
        self._host = os.environ.get("FUTU_HOST", "127.0.0.1")
        self._port = int(os.environ.get("FUTU_PORT", "11111"))

    def fetch(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        del fields
        if not codes:
            return {}
        validate_date_range(start_date, end_date)

        ktype = _to_futu_ktype(interval)
        ctx = futu.OpenQuoteContext(host=self._host, port=self._port)

        results: Dict[str, pd.DataFrame] = {}
        try:
            for code in codes:
                futu_code = _to_futu_symbol(code)
                ret, data = ctx.request_history_kline(
                    futu_code,
                    start=start_date,
                    end=end_date,
                    ktype=ktype,
                    max_count=10_000,
                )
                if ret != futu.RET_OK:
                    continue
                results[code] = _normalize_frame(data)
        finally:
            ctx.close()

        return results
