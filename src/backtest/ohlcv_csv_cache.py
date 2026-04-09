"""Persist exchange OHLCV under one folder so backtests reuse data without refetching.

Rolling window cache: ``{STEM}_{TIMEFRAME}.csv`` (e.g. ``BTC_USDT_1h.csv``).

Anchored range cache (walk-forward / eval): same folder, distinct names with epoch bounds —
``{STEM}_{TIMEFRAME}_{since_ms}_{until_ms}.csv`` so ranges never collide with rolling files.

Rows: ``timestamp_ms,open,high,low,close,volume`` (header row included).
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

from backtest.bars import (
    fetch_ccxt_ohlcv_bars,
    fetch_ccxt_ohlcv_range,
    nominal_interval_sec_for_timeframe,
)

CSV_HEADER = ("timestamp_ms", "open", "high", "low", "close", "volume")


def symbol_to_cache_stem(symbol: str) -> str:
    return symbol.strip().replace("/", "_").replace(":", "_")


def ohlcv_cache_path(cache_dir: Path, symbol: str, timeframe: str) -> Path:
    tf = (timeframe or "1d").strip().replace("/", "_")
    return Path(cache_dir) / f"{symbol_to_cache_stem(symbol)}_{tf}.csv"


def ohlcv_range_cache_path(
    cache_dir: Path, symbol: str, timeframe: str, *, since_ms: int, until_ms: int
) -> Path:
    tf = (timeframe or "1d").strip().replace("/", "_")
    stem = symbol_to_cache_stem(symbol)
    return Path(cache_dir) / f"{stem}_{tf}_{int(since_ms)}_{int(until_ms)}.csv"


def _parse_ohlcv_row(parts: list[str]) -> list[float]:
    return [
        float(parts[0]),
        float(parts[1]),
        float(parts[2]),
        float(parts[3]),
        float(parts[4]),
        float(parts[5]),
    ]


def load_ohlcv_csv(path: Path) -> list[list[float]]:
    if not path.is_file():
        raise FileNotFoundError(f"OHLCV CSV not found: {path}")
    rows: list[list[float]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for parts in reader:
            if len(parts) < 6:
                continue
            if parts[0].strip().lower() in ("timestamp_ms", "timestamp"):
                continue
            rows.append(_parse_ohlcv_row(parts))
    if len(rows) < 2:
        raise ValueError(f"CSV {path} has fewer than 2 data rows")
    rows.sort(key=lambda r: r[0])
    return rows


def save_ohlcv_csv(path: Path, bars: list[list[float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_HEADER)
        for row in bars:
            w.writerow([row[0], row[1], row[2], row[3], row[4], row[5]])


def ensure_bars_cached(
    symbol: str,
    limit: int,
    *,
    timeframe: str,
    exchange_id: str,
    cache_dir: Path,
    refresh: bool = False,
) -> list[list[float]]:
    """Return the last ``limit`` bars, loading from CSV when possible else fetch + save."""
    if limit < 2:
        raise ValueError("limit must be >= 2")
    path = ohlcv_cache_path(cache_dir, symbol, timeframe)
    if not refresh and path.is_file():
        try:
            loaded = load_ohlcv_csv(path)
            if len(loaded) >= limit:
                return loaded[-limit:]
        except (ValueError, OSError):
            pass
    # CCXT endpoints often cap a single `fetch_ohlcv(..., limit=N)` to 500–1000 rows.
    # For longer windows (e.g. 6 months of 1h ≈ 4320 bars), paginate a range and then
    # trim to the last `limit` bars before caching.
    if int(limit) > 1000:
        interval_sec = max(60, int(nominal_interval_sec_for_timeframe(timeframe)))
        until_ms = int(time.time() * 1000)
        # Add a small buffer so we still get >= limit rows even if there are gaps.
        since_ms = int(until_ms - (limit * interval_sec * 1000 * 1.1))
        bars = fetch_ccxt_ohlcv_range(
            symbol,
            timeframe=timeframe,
            since_ms=since_ms,
            until_ms=until_ms,
            exchange_id=exchange_id,
            max_rows=max(limit * 2, 2000),
        )[-limit:]
    else:
        bars = fetch_ccxt_ohlcv_bars(
            symbol,
            limit,
            timeframe=timeframe,
            exchange_id=exchange_id,
        )
    save_ohlcv_csv(path, bars)
    return bars


def load_bars_csv_only(
    symbol: str,
    limit: int,
    *,
    timeframe: str,
    cache_dir: Path,
) -> list[list[float]]:
    """Offline: read cache file only (no network)."""
    path = ohlcv_cache_path(cache_dir, symbol, timeframe)
    loaded = load_ohlcv_csv(path)
    if len(loaded) < limit:
        raise ValueError(
            f"{path} has {len(loaded)} rows but backtest needs {limit}; "
            "prefetch with python -m backtest.prefetch_ohlcv or use --online once."
        )
    return loaded[-limit:]


def ensure_range_cached(
    symbol: str,
    *,
    timeframe: str,
    since_ms: int,
    until_ms: int,
    exchange_id: str,
    cache_dir: Path,
    max_rows: int = 6000,
    refresh: bool = False,
) -> list[list[float]]:
    """Return OHLCV rows for a fixed anchored range, loading from CSV if present else fetch + save."""
    path = ohlcv_range_cache_path(
        cache_dir, symbol, timeframe, since_ms=since_ms, until_ms=until_ms
    )
    if not refresh and path.is_file():
        try:
            return load_ohlcv_csv(path)
        except (ValueError, OSError):
            pass
    bars = fetch_ccxt_ohlcv_range(
        symbol,
        timeframe=timeframe,
        since_ms=int(since_ms),
        until_ms=int(until_ms),
        exchange_id=exchange_id,
        max_rows=max(2, int(max_rows)),
    )
    save_ohlcv_csv(path, bars)
    return bars
