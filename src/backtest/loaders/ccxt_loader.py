"""CCXT-backed loader for crypto OHLCV data."""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import pandas as pd

from .base import NoAvailableSourceError, validate_date_range
from .registry import register

_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]
_INTERVAL_MAP = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1H": "1h",
    "4H": "4h",
    "1D": "1d",
    "1W": "1w",
    "1M": "1M",
}


@register
class CCXTLoader:
    """Fetch crypto OHLCV bars via CCXT (public, no API key needed)."""

    name = "ccxt"
    markets = {"crypto"}
    requires_auth = False

    def __init__(self) -> None:
        self._exchange_id = os.environ.get("CCXT_EXCHANGE", "binance")

    def is_available(self) -> bool:
        try:
            import ccxt  # noqa: PLC0415

            ex_class = getattr(ccxt, self._exchange_id, None)
            return ex_class is not None
        except ImportError:
            return False

    def fetch(
        self,
        codes: list[str],
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

        import ccxt  # noqa: PLC0415

        ex_class = getattr(ccxt, self._exchange_id, None)
        if ex_class is None:
            raise NoAvailableSourceError(f"Unknown exchange: {self._exchange_id}")
        exchange = ex_class({"enableRateLimit": True})
        exchange.load_markets()

        timeframe = _INTERVAL_MAP.get(interval.strip(), "1d")
        since_ms = int(pd.Timestamp(start_date).timestamp() * 1000)
        until_ms = int(pd.Timestamp(end_date).timestamp() * 1000)

        results: Dict[str, pd.DataFrame] = {}
        for code in codes:
            resolved = self._resolve_symbol(exchange, code)
            if resolved not in exchange.symbols:
                print(f"[WARN] Symbol {code} not on {self._exchange_id}, skipping")
                continue
            try:
                raw = self._fetch_range(exchange, resolved, timeframe, since_ms, until_ms)
            except Exception as exc:
                print(f"[WARN] Failed to fetch {code}: {exc}")
                continue
            if not raw:
                continue
            results[code] = self._to_dataframe(raw)
        return results

    @staticmethod
    def _resolve_symbol(exchange, symbol: str) -> str:
        if symbol in exchange.symbols:
            return symbol
        s = symbol.strip()
        if s.endswith("/USDT") and f"{s}:USDT" in exchange.symbols:
            return f"{s}:USDT"
        return symbol

    @staticmethod
    def _fetch_range(
        exchange, symbol: str, timeframe: str, since_ms: int, until_ms: int
    ) -> list[list[float]]:
        out: list[list[float]] = []
        cursor = since_ms
        while cursor < until_ms:
            batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=cursor, limit=1000)
            if not batch:
                break
            for row in batch:
                ts = int(row[0])
                if ts < since_ms:
                    continue
                if ts > until_ms:
                    continue
                out.append([float(v) for v in row])
            last_ts = int(batch[-1][0])
            if last_ts <= cursor:
                break
            cursor = last_ts + 1
            if len(batch) < 1000:
                break
        out.sort(key=lambda r: r[0])
        return out

    @staticmethod
    def _to_dataframe(raw: list[list[float]]) -> pd.DataFrame:
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        df.index.name = "trade_date"
        return df[_OHLCV_COLUMNS]
