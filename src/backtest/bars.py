"""OHLCV bar series for multi-step backtests (synthetic or file-backed)."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any


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
