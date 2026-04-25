"""Yahoo Finance-backed loader for global equity OHLCV data."""

from __future__ import annotations

from typing import Dict, List, Optional

import pandas as pd

from .base import NoAvailableSourceError, validate_date_range
from .registry import register

_OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


@register
class YFinanceLoader:
    """Fetch global equity bars via yfinance (free, no API key needed)."""

    name = "yfinance"
    markets = {"hk_equity", "us_equity", "a_share"}
    requires_auth = False

    def is_available(self) -> bool:
        import importlib.util

        return importlib.util.find_spec("yfinance") is not None

    def fetch(
        self,
        codes: list[str],
        start_date: str,
        end_date: str,
        *,
        interval: str = "1D",
        fields: Optional[List[str]] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch OHLCV history from Yahoo Finance.

        Args:
            codes: Yahoo ticker symbols e.g. ``0700.HK``, ``0005.HK``, ``AAPL``.
            start_date: Start date ``YYYY-MM-DD``.
            end_date: End date ``YYYY-MM-DD``.
            interval: Supported: ``1D``, ``1H``.

        Returns:
            {symbol: DataFrame[trade_date, open, high, low, close, volume]}
        """
        del fields
        if not codes:
            return {}
        validate_date_range(start_date, end_date)

        try:
            import yfinance as yf  # noqa: PLC0415
        except ImportError as exc:
            raise NoAvailableSourceError("yfinance not installed") from exc

        _interval_map = {"1D": "1d", "1H": "60m", "4H": "1d"}
        yf_interval = _interval_map.get(interval.strip(), "1d")

        results: Dict[str, pd.DataFrame] = {}
        for code in codes:
            try:
                ticker = yf.Ticker(code)
                hist = ticker.history(
                    start=start_date,
                    end=end_date,
                    interval=yf_interval,
                    auto_adjust=True,
                )
            except Exception as exc:
                print(f"[WARN] yfinance failed for {code}: {exc}")
                continue

            if hist.empty:
                continue

            df = hist[["Open", "High", "Low", "Close", "Volume"]].copy()
            df.columns = _OHLCV_COLUMNS
            df.index.name = "trade_date"
            df["volume"] = df["volume"].fillna(0.0)
            results[code] = df

        return results
