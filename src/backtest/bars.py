"""OHLCV bar series for multi-step backtests (synthetic, exchange-backed, or file-backed)."""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import ccxt


def _resolve_ccxt_symbol(exchange: ccxt.Exchange, symbol: str) -> str:
    """Resolve common Binance linear-swap aliases (``BASE/USDT:USDT``) when spot ``BASE/USDT`` is absent."""
    if symbol in exchange.symbols:
        return symbol
    s = (symbol or "").strip()
    if s.endswith("/USDT"):
        alias = f"{s}:USDT"
        if alias in exchange.symbols:
            return alias
    return symbol


def iso_utc_to_ms(iso_date: str) -> int:
    """Parse ``YYYY-MM-DD`` or ISO datetime into epoch milliseconds (UTC)."""
    s = (iso_date or "").strip()
    if "T" not in s and len(s) <= 10:
        s = f"{s}T00:00:00+00:00"
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def interval_sec_to_ccxt_timeframe(interval_sec: int) -> str:
    """Map bar length to a CCXT timeframe string (falls back to ``1d``).

    ``2592000`` is treated as **~30d** and maps to exchange **monthly** (``1M``) candles.
    """
    return {
        60: "1m",
        180: "3m",
        300: "5m",
        900: "15m",
        1800: "30m",
        3600: "1h",
        14400: "4h",
        86400: "1d",
        604800: "1w",
        2_592_000: "1M",
    }.get(int(interval_sec), "1d")


def nominal_interval_sec_for_timeframe(tf: str) -> int:
    """Approximate spacing in seconds for labeling / synthetic bars when using explicit CCXT tf."""
    key = (tf or "1d").strip()
    return {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
        "1w": 604800,
        "1M": 2_592_000,
    }.get(key, 86400)


def fetch_ccxt_ohlcv_bars(
    symbol: str,
    limit: int,
    *,
    timeframe: str = "1d",
    exchange_id: str = "binance",
) -> list[list[float]]:
    """Fetch the last ``limit`` candles from a public exchange (no API keys required for OHLCV).

    Returns CCXT rows ``[ts_ms, open, high, low, close, volume]`` (same as synthetic helpers).
    """
    if limit < 2:
        raise ValueError("limit must be >= 2")
    ex_class = getattr(ccxt, exchange_id)
    exchange = ex_class({"enableRateLimit": True})
    exchange.load_markets()
    resolved = _resolve_ccxt_symbol(exchange, symbol)
    if resolved not in exchange.symbols:
        raise ValueError(f"Symbol {symbol!r} not on {exchange_id}; check spelling (e.g. BTC/USDT).")
    raw = exchange.fetch_ohlcv(resolved, timeframe=timeframe, limit=int(limit))
    if len(raw) < 2:
        raise RuntimeError(f"Exchange returned {len(raw)} rows; need at least 2.")
    return [list(row) for row in raw]


def fetch_ccxt_ohlcv_range(
    symbol: str,
    *,
    timeframe: str = "1d",
    since_ms: int,
    until_ms: int,
    exchange_id: str = "binance",
    max_rows: int = 5000,
) -> list[list[float]]:
    """Fetch OHLCV for **[since_ms, until_ms]** (inclusive close time), UTC.

    Paginates exchange pages (typically 500–1000 rows) so windows are **reproducible**
    unlike ``fetch_ohlcv(..., limit=N)`` alone (which drifts as "last N candles").
    """
    if since_ms >= until_ms:
        raise ValueError("since_ms must be < until_ms")
    ex_class = getattr(ccxt, exchange_id)
    exchange = ex_class({"enableRateLimit": True})
    exchange.load_markets()
    resolved = _resolve_ccxt_symbol(exchange, symbol)
    if resolved not in exchange.symbols:
        raise ValueError(f"Symbol {symbol!r} not on {exchange_id}; check spelling (e.g. BTC/USDT).")
    cap = max(2, int(max_rows))
    out: list[list[float]] = []
    cursor = int(since_ms)
    page_limit = 1000

    while cursor < until_ms and len(out) < cap:
        batch = exchange.fetch_ohlcv(resolved, timeframe=timeframe, since=cursor, limit=page_limit)
        if not batch:
            break
        for row in batch:
            ts = int(row[0])
            if ts < since_ms:
                continue
            if ts > until_ms:
                continue
            out.append(list(row))
        last_ts = int(batch[-1][0])
        if last_ts <= cursor:
            break
        cursor = last_ts + 1
        if len(batch) < page_limit:
            break

    if len(out) < 2:
        raise RuntimeError(
            f"Range {since_ms}–{until_ms} returned {len(out)} rows; need at least 2 for backtest."
        )
    out.sort(key=lambda r: r[0])
    return out[:cap]


def align_bars_by_min_length(
    bars_by_symbol: dict[str, list[list[float]]],
) -> dict[str, list[list[float]]]:
    """Trim each OHLCV series to the same length using the **last** ``min(len)`` rows.

    Assumes rows are time-ordered and comparable bar-by-bar (same timeframe / cadence).
    """
    if not bars_by_symbol:
        raise ValueError("bars_by_symbol must be non-empty")
    n = min(len(v) for v in bars_by_symbol.values())
    if n < 2:
        raise ValueError("each symbol needs at least 2 bars after alignment")
    return {sym: rows[-n:] for sym, rows in bars_by_symbol.items()}


def synthetic_ohlcv_bars(
    n: int,
    *,
    seed: int = 42,
    start_ts_ms: int = 1_700_000_000_000,
    interval_sec: int = 300,
) -> list[list[float]]:
    """
    Build ``n`` CCXT-style OHLCV rows: ``[ts_ms, open, high, low, close, volume]``.

    ``interval_sec`` defaults to 300 (5 minutes), matching a typical scan cadence.
    """
    rng = random.Random(seed)
    step_ms = interval_sec * 1000
    bars: list[list[float]] = []
    price = 100.0
    for i in range(n):
        ret = rng.uniform(-0.003, 0.003)
        o = price
        price = max(1e-9, price * (1 + ret))
        c = price
        h = max(o, c) * (1 + abs(rng.uniform(0, 0.0005)))
        lo = min(o, c) * (1 - abs(rng.uniform(0, 0.0005)))
        v = rng.uniform(0.1, 5.0)
        bars.append([float(start_ts_ms + i * step_ms), o, h, lo, c, v])
    return bars


def trending_ohlcv_bars(
    n: int,
    *,
    seed: int = 42,
    start_ts_ms: int = 1_700_000_000_000,
    interval_sec: int = 86_400,
    drift_per_bar: float = 0.006,
    noise: float = 0.002,
) -> list[list[float]]:
    """``n`` daily-style bars with positive drift so TA / consensus skew constructive (backtests).

    ``interval_sec`` defaults to 86400 (1d). ``drift_per_bar`` is approximate mean log return per bar.
    """
    rng = random.Random(seed)
    step_ms = interval_sec * 1000
    bars: list[list[float]] = []
    price = 50_000.0
    for i in range(n):
        r = drift_per_bar + rng.uniform(-noise, noise)
        o = price
        price = max(1e-9, price * (1.0 + r))
        c = price
        h = max(o, c) * (1.0 + abs(rng.uniform(0, 0.001)))
        lo = min(o, c) * (1.0 - abs(rng.uniform(0, 0.001)))
        v = rng.uniform(10.0, 500.0)
        bars.append([float(start_ts_ms + i * step_ms), o, h, lo, c, v])
    return bars


def load_ohlcv_json(path: Path) -> tuple[str, list[list[Any]]]:
    """
    Load JSON file: ``{"ticker": "...", "bars": [[ts,o,h,l,c,v], ...]}`` or
    ``{"ticker": "...", "ohlcv": [...]}``.
    """
    data = json.loads(path.read_text())
    ticker = str(data.get("ticker") or "BTC/USDT")
    raw = data.get("bars") or data.get("ohlcv")
    if not isinstance(raw, list) or not raw:
        raise ValueError("JSON must contain a non-empty 'bars' or 'ohlcv' array")
    return ticker, raw


def load_multi_ohlcv_json(path: Path) -> dict[str, list[list[Any]]]:
    """Load ``{"bars_by_symbol": {"BTC/USDT": [...], "ETH/USDT": [...]}}`` for multi-asset tests."""
    data = json.loads(path.read_text())
    raw = data.get("bars_by_symbol")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("JSON must contain a non-empty object 'bars_by_symbol'")
    out: dict[str, list[list[Any]]] = {}
    for k, v in raw.items():
        if not isinstance(v, list) or not v:
            raise ValueError(f"bars_by_symbol[{k!r}] must be a non-empty list")
        out[str(k)] = v
    return out
