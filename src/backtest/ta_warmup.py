"""TA warmup: prefetch extra OHLCV bars for indicators; no trades/LLM in that window."""

from __future__ import annotations

from typing import Sequence

from config.app_settings import load_app_settings

# MACD(12,26,9) stabilizes around 40 daily bars (see tools/technical_indicators.py).
DEFAULT_TA_WARMUP_BARS = 50


def resolve_ta_warmup_bars(*, override: int | None = None) -> int:
    """Bars prefetched before the evaluation window (no LLM, no trades)."""
    if override is not None:
        return max(0, int(override))
    app = load_app_settings()
    w = int(getattr(app.backtest, "min_warmup_bars", 0) or 0)
    return max(0, w if w > 0 else DEFAULT_TA_WARMUP_BARS)


def total_fetch_bars(*, eval_steps: int, warmup_bars: int | None = None) -> tuple[int, int]:
    """Return ``(fetch_limit, warmup_bars)`` for OHLCV loaders."""
    ev = max(2, int(eval_steps))
    w = resolve_ta_warmup_bars(override=warmup_bars)
    return ev + w, w


def warmup_fetch_since_ms(
    *,
    eval_since_ms: int,
    interval_sec: int,
    warmup_bars: int | None = None,
) -> tuple[int, int]:
    """Extend ``eval_since`` backward by warmup bars so From→To stays fully scored.

    Returns ``(fetch_since_ms, planned_warmup_bars)``.
    """
    w = resolve_ta_warmup_bars(override=warmup_bars)
    interval_ms = max(1, int(interval_sec) * 1000)
    return max(0, int(eval_since_ms) - w * interval_ms), w


def split_warmup_index(
    bars: Sequence[Sequence[float]],
    *,
    eval_since_ms: int,
) -> int:
    """Index of the first bar at/after ``eval_since_ms`` (warmup length = that index)."""
    for i, row in enumerate(bars):
        if not row:
            continue
        if int(row[0]) >= int(eval_since_ms):
            return i
    return len(bars)


__all__ = [
    "DEFAULT_TA_WARMUP_BARS",
    "resolve_ta_warmup_bars",
    "total_fetch_bars",
    "warmup_fetch_since_ms",
    "split_warmup_index",
]
