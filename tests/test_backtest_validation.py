"""Tests for backtest quality validation module."""

from __future__ import annotations

import random

from backtest.validation import (
    MarketRegime,
    check_exit_reason_distribution,
    check_profit_loss_ratio,
    detect_market_regime,
    generate_quality_report,
    regime_coverage_check,
    split_forward_validation,
    validate_sample_size,
)


class TestDetectMarketRegime:
    def test_bull_market(self):
        prices = [100.0 * (1 + 0.003) ** i for i in range(100)]  # ~35% up, low vol
        regime = detect_market_regime(prices)
        assert regime.label == "bull"

    def test_bear_market(self):
        prices = [100.0 * (1 - 0.003) ** i for i in range(100)]  # ~26% down
        regime = detect_market_regime(prices)
        assert regime.label == "bear"

    def test_sideways_market(self):
        import random

        random.seed(42)
        prices = [100.0 + random.uniform(-2, 2) for _ in range(100)]
        regime = detect_market_regime(prices)
        assert regime.label == "sideways"

    def test_insufficient_data(self):
        prices = [100.0, 101.0]
        regime = detect_market_regime(prices)
        assert regime.label == "sideways"


class TestRegimeCoverage:
    def test_single_regime_fails(self):
        result = regime_coverage_check([MarketRegime("bull", 20.0, 15.0)])
        assert not result["passed"]
        assert result["count"] == 1

    def test_two_regimes_passes(self):
        result = regime_coverage_check(
            [
                MarketRegime("bull", 20.0, 15.0),
                MarketRegime("bear", -15.0, 30.0),
            ]
        )
        assert result["passed"]
        assert result["count"] == 2


class TestSampleSize:
    def test_sufficient(self):
        result = validate_sample_size(200, 50)
        assert result.passed
        assert result.warning is None

    def test_too_few_bars(self):
        result = validate_sample_size(50, 30)
        assert not result.passed
        assert not result.min_bars_ok

    def test_too_few_trades(self):
        result = validate_sample_size(200, 5)
        assert not result.passed
        assert not result.min_trades_ok
        assert "trades" in (result.warning or "")


class TestProfitLossRatio:
    def test_passes_threshold(self):
        result = check_profit_loss_ratio(2.0)
        assert result.passed

    def test_fails_below_threshold(self):
        result = check_profit_loss_ratio(1.1)
        assert not result.passed
        assert "1.3" in (result.warning or "")

    def test_no_trades_does_not_fail(self):
        result = check_profit_loss_ratio(None)
        assert result.passed

    def test_no_losing_trades(self):
        result = check_profit_loss_ratio(999.0)
        assert result.passed
        assert result.warning is not None
        assert "profit factor extreme" in result.warning.lower()


class TestExitReasonDistribution:
    def test_healthy_mix(self):
        trades = [
            {"exit_reason": "take_profit"},
            {"exit_reason": "take_profit"},
            {"exit_reason": "signal"},
            {"exit_reason": "signal"},
            {"exit_reason": "signal"},
            {"exit_reason": "stop_loss"},
            {"exit_reason": "end_of_backtest"},
        ]
        result = check_exit_reason_distribution(trades)
        assert result.passed

    def test_too_many_liquidations(self):
        trades = [{"exit_reason": "liquidation"} for _ in range(10)]
        result = check_exit_reason_distribution(trades)
        assert not result.passed
        assert "Liquidation" in (result.warning or "")

    def test_no_risk_controls(self):
        trades = [{"exit_reason": "signal"} for _ in range(20)]
        result = check_exit_reason_distribution(trades)
        assert not result.passed

    def test_unknown_reasons(self):
        result = check_exit_reason_distribution([])
        # Empty list: score=0.50 at threshold, total=0 < 4 → no warning, passed=True
        assert result.passed


class TestForwardValidationSplit:
    def test_split_correct(self):
        bars = {"BTC/USDT": [[i, 100, 101, 99, 100 + i * 0.1, 10] for i in range(100)]}
        is_bars, oos_bars = split_forward_validation(bars, oos_bars=30)
        assert len(is_bars["BTC/USDT"]) == 70
        assert len(oos_bars["BTC/USDT"]) == 30

    def test_no_split_when_too_few_bars(self):
        # When total bars < oos_bars, split at max(1, n - oos_bars) = max(1, -25) = 1
        # So 1 bar goes IS, remaining go OOS
        bars = {"BTC/USDT": [[i, 100, 101, 99, 100, 10] for i in range(5)]}
        is_bars, oos_bars = split_forward_validation(bars, oos_bars=30)
        assert len(is_bars["BTC/USDT"]) == 1
        assert len(oos_bars["BTC/USDT"]) == 4


class TestFullQualityReport:
    def test_generate_report(self):
        # Use enough trades (30+) to pass sample size check
        closes = [100.0 * (1 + random.uniform(-0.01, 0.015)) for _ in range(200)]
        import random as rng

        rng.seed(42)
        reasons = [
            "take_profit",
            "take_profit",
            "take_profit",
            "signal",
            "signal",
            "signal",
            "signal",
            "stop_loss",
            "end_of_backtest",
            "take_profit",
            "take_profit",
            "signal",
            "signal",
            "signal",
            "signal",
            "stop_loss",
            "end_of_backtest",
            "take_profit",
            "signal",
            "signal",
            "signal",
            "stop_loss",
            "signal",
            "signal",
            "take_profit",
            "take_profit",
            "signal",
            "end_of_backtest",
            "signal",
            "signal",
            "signal",
            "stop_loss",
            "take_profit",
            "signal",
            "signal",
        ]
        trades = [{"exit_reason": r, "pnl": rng.uniform(-30, 60)} for r in reasons]
        # Need different market regimes - use mixture
        closes_mixed = (
            list(reversed(closes))[:100] + closes[100:200]
        )  # bearish then bullish = 2 regimes
        report = generate_quality_report(
            close_prices=closes_mixed,
            total_bars=200,
            trade_count=len(trades),
            profit_factor=2.5,
            trades=trades,
        )
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "regime_coverage" in d
        assert "sample_size" in d
        assert "profit_loss_ratio" in d
        assert "exit_reasons" in d

    def test_report_with_warnings(self):
        closes = [100.0 for _ in range(50)]  # sideways, too few bars
        trades = [{"exit_reason": "signal"} for _ in range(5)]
        report = generate_quality_report(
            close_prices=closes,
            total_bars=50,
            trade_count=5,
            profit_factor=0.8,
            trades=trades,
        )
        assert len(report.warnings) > 0
        assert not report.overall_passed
