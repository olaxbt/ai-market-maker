from backtest.metrics import (
    compute_basic_metrics,
    max_drawdown,
    returns_from_equity,
    sharpe_ratio,
    win_rate,
)


def test_max_drawdown_basic():
    assert max_drawdown([100, 110, 105, 120, 90, 130]) == (120 - 90) / 120


def test_returns_from_equity():
    assert returns_from_equity([100, 110, 99]) == [0.1, -0.1]


def test_sharpe_zero_when_flat():
    assert sharpe_ratio([0.0, 0.0, 0.0]) == 0.0


def test_win_rate():
    assert win_rate([1, -1, 2, 0]) == 0.5


def test_compute_basic_metrics_smoke():
    m = compute_basic_metrics(
        equity_curve=[100, 110, 105, 115],
        trade_pnls=[1, -1, 0.5],
        interval_sec=86_400,
    )
    assert m.max_drawdown > 0
    assert isinstance(m.sharpe, float)
    assert isinstance(m.sortino, float)
    assert 0 <= m.win_rate <= 1
    assert m.periods_per_year >= 300
    assert m.profit_factor is not None
