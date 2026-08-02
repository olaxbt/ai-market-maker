"""OHLCV bar series for multi-step backtests (exchange-backed or file-backed)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import ccxt


def _resolve_ccxt_symbol(exchange: Any, symbol: str) -> str:
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


def interval_sec_to_futu_interval(interval_sec: int) -> str:
    """Map bar length in seconds to :meth:`FutuAdapter.get_history_kline` interval strings.

    Monthly (~30d) uses ``1mon`` to avoid clashing with minute ``1m``.
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
        2_592_000: "1mon",
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


def fetch_futu_ohlcv_bars(
    symbol: str,
    limit: int,
    *,
    interval_sec: int = 86400,
) -> list[list[float]]:
    """Fetch the last ``limit`` candles from Futu OpenD (HK/US equities, etc.).

    Requires ``futu-api``, OpenD reachable at ``FUTU_OPEND_HOST`` / ``FUTU_OPEND_QUOTE_PORT``.
    Returns rows ``[ts_ms, open, high, low, close, volume]`` like CCXT helpers.
    """
    if limit < 2:
        raise ValueError("limit must be >= 2")
    from adapters.futu import FutuAdapter, normalize_futu_symbol

    futu_interval = interval_sec_to_futu_interval(int(interval_sec))
    nsym = normalize_futu_symbol(symbol)
    adapter: Any = None
    try:
        adapter = FutuAdapter()
        raw = adapter.get_history_kline(symbol=nsym, interval=futu_interval, limit=int(limit))
    finally:
        if adapter is not None and hasattr(adapter, "close"):
            adapter.close()
    if len(raw) < 2:
        raise RuntimeError(f"Futu returned {len(raw)} rows for {nsym!r}; need at least 2.")
    return [list(map(float, row)) for row in raw]


def normalize_yfinance_symbol(symbol: str) -> str:
    """Map UI / Futu-style codes to Yahoo Finance tickers."""
    s = (symbol or "").strip()
    if not s:
        raise ValueError("symbol is required")
    upper = s.upper()
    if "/" in upper:
        base, quote = upper.split("/", 1)
        quote = quote.split(":")[0]
        if quote in ("USDT", "USD", "USDC"):
            return f"{base}-USD"
        return f"{base}-{quote}"
    if upper.startswith("US."):
        return upper[3:]
    if upper.startswith("HK."):
        digits = "".join(ch for ch in upper[3:] if ch.isdigit()).lstrip("0") or "0"
        return f"{digits.zfill(4)}.HK"
    return s


def interval_sec_to_yfinance_interval(interval_sec: int) -> str:
    """Map bar length to a yfinance interval string."""
    return {
        60: "1m",
        120: "2m",
        300: "5m",
        900: "15m",
        1800: "30m",
        3600: "60m",
        5400: "90m",
        86400: "1d",
        604800: "1wk",
        2_592_000: "1mo",
    }.get(int(interval_sec), "1d")


def _yfinance_period_candidates(yf_interval: str, limit: int) -> list[str]:
    """Yahoo intraday history is capped (≈7d for 1m, ≈60d for 2m–90m). Prefer short periods first."""
    lim = max(2, int(limit))
    iv = (yf_interval or "1d").strip()
    if iv == "1m":
        return ["7d", "5d"]
    if iv in {"2m", "5m", "15m", "30m", "60m", "90m"}:
        return ["60d", "30d", "7d"]
    if lim > 400:
        return ["max", "10y", "5y", "2y"]
    if lim > 60:
        return ["2y", "1y", "6mo"]
    return ["6mo", "3mo", "1mo", "5d"]


def fetch_yfinance_ohlcv_bars(
    symbol: str,
    limit: int,
    *,
    interval_sec: int = 86400,
    since_ms: int | None = None,
    until_ms: int | None = None,
) -> list[list[float]]:
    """Fetch OHLCV from Yahoo Finance (no API key). Futu-free equity / crypto fallback.

    Returns rows ``[ts_ms, open, high, low, close, volume]`` like CCXT helpers.

    Note: Yahoo only serves short windows for intraday intervals (e.g. 5m/15m ≈ last 60d).
    Using a multi-year ``period`` with those intervals returns an empty frame — we pick a
    compatible period and retry shorter windows before failing.
    """
    if limit < 2:
        raise ValueError("limit must be >= 2")
    import yfinance as yf

    yf_sym = normalize_yfinance_symbol(symbol)
    yf_interval = interval_sec_to_yfinance_interval(int(interval_sec))
    ticker = yf.Ticker(yf_sym)
    last_err: str | None = None
    hist = None

    if since_ms is not None and until_ms is not None:
        if since_ms >= until_ms:
            raise ValueError("since_ms must be < until_ms")
        span_days = (until_ms - since_ms) / 86_400_000.0
        if yf_interval == "1m" and span_days > 7.5:
            raise ValueError(
                f"Yahoo 1m bars only cover ~7 days (requested ~{span_days:.0f}d). "
                "Shorten the date range or use a daily interval."
            )
        if yf_interval in {"2m", "5m", "15m", "30m", "60m", "90m"} and span_days > 60.5:
            raise ValueError(
                f"Yahoo {yf_interval} bars only cover ~60 days (requested ~{span_days:.0f}d). "
                "Shorten the date range or use interval=1d."
            )
        start = datetime.fromtimestamp(since_ms / 1000.0, tz=timezone.utc)
        end = datetime.fromtimestamp(until_ms / 1000.0, tz=timezone.utc)
        # Yahoo ``end`` is exclusive for daily bars; nudge +1 day so until_iso is inclusive.
        end_s = (
            (end + timedelta(days=1)).strftime("%Y-%m-%d")
            if yf_interval in {"1d", "1wk", "1mo"}
            else end.strftime("%Y-%m-%d")
        )
        try:
            hist = ticker.history(
                start=start.strftime("%Y-%m-%d"),
                end=end_s,
                interval=yf_interval,
                auto_adjust=True,
            )
        except Exception as exc:  # noqa: BLE001 — surface Yahoo/network errors clearly
            last_err = str(exc)
            hist = None
    else:
        for period in _yfinance_period_candidates(yf_interval, int(limit)):
            try:
                cand = ticker.history(period=period, interval=yf_interval, auto_adjust=True)
            except Exception as exc:  # noqa: BLE001
                last_err = str(exc)
                continue
            if cand is not None and not cand.empty:
                hist = cand
                break
            last_err = f"empty for period={period!r} interval={yf_interval!r}"

    if hist is None or hist.empty:
        hint = (
            "Yahoo intraday (5m/15m/…) only covers recent weeks — use 1d bars, "
            "or Latest-N with a short window."
            if yf_interval not in {"1d", "1wk", "1mo"}
            else "Check the ticker spelling / network access to Yahoo."
        )
        detail = f" ({last_err})" if last_err else ""
        raise RuntimeError(f"Yahoo Finance returned no rows for {yf_sym!r}{detail}. {hint}")

    rows: list[list[float]] = []
    for idx, row in hist.iterrows():
        ts = idx
        if getattr(ts, "tzinfo", None) is None:
            ts_ms = int(datetime(ts.year, ts.month, ts.day, tzinfo=timezone.utc).timestamp() * 1000)
        else:
            ts_ms = int(ts.timestamp() * 1000)
        rows.append(
            [
                float(ts_ms),
                float(row["Open"]),
                float(row["High"]),
                float(row["Low"]),
                float(row["Close"]),
                float(row.get("Volume") or 0.0),
            ]
        )
    if since_ms is None and until_ms is None and len(rows) > int(limit):
        rows = rows[-int(limit) :]
    if len(rows) < 2:
        raise RuntimeError(
            f"Yahoo Finance returned {len(rows)} rows for {yf_sym!r}; need at least 2."
        )
    return rows


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
