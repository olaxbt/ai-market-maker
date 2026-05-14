"""Bar spacing inference for Sharpe annualization (PerpEngine)."""

from backtest.engines.perp import EquitySnapshot, PerpEngine


def _snap(ts_ms: int, eq: float = 10_000.0) -> EquitySnapshot:
    return EquitySnapshot(
        timestamp=ts_ms,
        capital=eq,
        unrealized_pnl=0.0,
        equity=eq,
        position_count=0,
    )


def test_infer_daily_ms_timestamps():
    eng = PerpEngine({"interval_sec": 86_400})
    t0 = 1_738_540_800_000  # arbitrary modern ms
    eng.snapshots = [_snap(t0 + i * 86_400_000) for i in range(10)]
    assert eng._infer_bar_interval_sec_from_snapshots() == 86_400


def test_infer_daily_unix_seconds_timestamps():
    """Seconds-based OHLCV must not be divided by 1000 (would look like ~86s bars)."""
    eng = PerpEngine({"interval_sec": 86_400})
    t0 = 1_738_540_800  # same instant in seconds
    eng.snapshots = [_snap(t0 + i * 86_400) for i in range(10)]
    assert eng._infer_bar_interval_sec_from_snapshots() == 86_400


def test_infer_reconciles_when_median_far_below_configured_bar():
    """Mis-inferred sub-hour spacing vs configured daily → trust interval_sec."""
    eng = PerpEngine({"interval_sec": 86_400})
    # Simulate broken deltas that would median to ~90s while caller knows bars are 1d.
    t0 = 1_738_540_800_000
    deltas_ms = [86_400_000] * 3 + [90_000] * 10  # contaminate median toward 90s in ms space
    ts = t0
    eng.snapshots = []
    for d in deltas_ms:
        eng.snapshots.append(_snap(ts))
        ts += d
    med_raw = eng._infer_bar_interval_sec_from_snapshots()
    assert med_raw == 86_400
