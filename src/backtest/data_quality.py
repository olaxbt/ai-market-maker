"""OHLCV data-integrity validation for backtest windows.

Checks that the bars fed to agents are sane before inference:
- Monotonic timestamps
- No gaps larger than expected interval
- Minimum bar count
- Ticker consistency

"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OhlcvQualityResult:
    """Result of a single OHLCV window validation."""

    passed: bool
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)


def validate_ohlcv_window(
    ohlcv: list,
    *,
    symbol: str,
    expected_ticker: str,
    interval_sec: int,
    min_bars: int = 2,
) -> OhlcvQualityResult:
    """Validate an OHLCV bar window for data integrity.

    Parameters
    ----------
    ohlcv : list
        List of OHLCV bars, each as ``[ts_ms_or_sec, o, h, l, c, v]``.
    symbol : str
        The symbol being validated (for warning messages).
    expected_ticker : str
        The ticker string the engine expects (may be identical to symbol).
    interval_sec : int
        Expected bar interval in seconds.
    min_bars : int
        Minimum bar count required (default 2).

    Returns
    -------
    OhlcvQualityResult with ``passed``, ``warnings``, and ``checks`` dict.
    """
    if not ohlcv or not isinstance(ohlcv, list):
        return OhlcvQualityResult(
            passed=False,
            warnings=[f"{symbol}: empty or invalid OHLCV window"],
            checks={"has_data": False, "monotonic_ts": False, "gap_ok": False, "min_bars": False},
        )

    checks: dict[str, bool] = {}
    warnings: list[str] = []

    # Minimum bar count
    n = len(ohlcv)
    checks["min_bars"] = n >= min_bars
    if not checks["min_bars"]:
        warnings.append(f"{symbol}: only {n} bars, need ≥{min_bars}")

    # — parse timestamps (support ms or sec) —
    ts_list: list[float] = []
    for row in ohlcv:
        try:
            ts = float(row[0])
        except (IndexError, TypeError, ValueError):
            ts = 0.0
        ts_list.append(ts)

    # Normalise to milliseconds for comparison
    if ts_list:
        first_ts = ts_list[0]
        if 1e10 < first_ts < 1e13:
            # Already in ms
            pass
        elif 1e8 < first_ts < 1e10:
            # Seconds → ms
            ts_list = [t * 1000.0 for t in ts_list]

    # Monotonic timestamps
    monotonic = True
    for i in range(1, len(ts_list)):
        if ts_list[i] < ts_list[i - 1]:
            monotonic = False
            break
    checks["monotonic_ts"] = monotonic
    if not monotonic:
        warnings.append(f"{symbol}: non-monotonic timestamps detected")

    # Gap check: no gap > 1.5× interval_sec
    gap_ok = True
    if len(ts_list) >= 2 and monotonic:
        interval_ms = interval_sec * 1000
        max_gap_ms = int(interval_ms * 1.5)
        for i in range(1, len(ts_list)):
            gap = int(ts_list[i] - ts_list[i - 1])
            if gap > max_gap_ms:
                gap_ok = False
                # Only report the first gap to avoid noise
                warnings.append(
                    f"{symbol}: gap of {gap}ms at bar {i} "
                    f"(> {max_gap_ms}ms, expected ~{interval_ms}ms)"
                )
                break
    checks["gap_ok"] = gap_ok

    # Ticker match
    ticker_match = symbol == expected_ticker
    checks["ticker_match"] = ticker_match
    if not ticker_match:
        warnings.append(f"{symbol}: ticker mismatch (expected {expected_ticker})")

    # Data presence
    checks["has_data"] = n > 0

    passed = all(v for v in checks.values())
    return OhlcvQualityResult(passed=passed, warnings=warnings, checks=checks)
