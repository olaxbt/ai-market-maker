"""Backtest quality checks: sample size, regimes, profit factor, forward OOS, exits."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Sequence


@dataclass(frozen=True)
class MarketRegime:
    label: str  # "bull", "bear", "sideways"
    total_return_pct: float
    volatility_pct: float


def detect_market_regime(
    close_prices: Sequence[float],
    *,
    ret_threshold_pct: float = 15.0,
    vol_threshold_pct: float = 25.0,
) -> MarketRegime:
    """Classify a price series as bull / bear / sideways.

    Parameters
    ----------
    close_prices : sequence of closing prices.
    ret_threshold_pct : minimum total return (%) to qualify as directional.
    vol_threshold_pct : minimum annualized vol (%) to override directional label.

    Returns
    -------
    MarketRegime with label + descriptive stats.
    """
    xs = [float(x) for x in close_prices if x > 0]
    if len(xs) < 10:
        return MarketRegime(label="sideways", total_return_pct=0.0, volatility_pct=0.0)

    total_ret = (xs[-1] / xs[0] - 1.0) * 100.0

    # Approximate daily volatility from log returns
    log_rets = []
    for a, b in zip(xs, xs[1:], strict=False):
        if a > 0 and b > 0:
            log_rets.append(math.log(b / a))
    if not log_rets:
        return MarketRegime(label="sideways", total_return_pct=total_ret, volatility_pct=0.0)

    mean_lr = sum(log_rets) / len(log_rets)
    var_lr = (
        sum((x - mean_lr) ** 2 for x in log_rets) / (len(log_rets) - 1)
        if len(log_rets) > 1
        else 0.0
    )
    daily_vol = math.sqrt(max(0.0, var_lr))
    # Annualize approx (treat as daily bars, * sqrt(365))
    ann_vol_pct = daily_vol * math.sqrt(365.0) * 100.0

    if ann_vol_pct > vol_threshold_pct:
        # High vol → directional classification based on return sign
        label = (
            "bull"
            if total_ret > vol_threshold_pct * 0.3
            else ("bear" if total_ret < -vol_threshold_pct * 0.3 else "sideways")
        )
    else:
        label = (
            "bull"
            if total_ret > ret_threshold_pct
            else ("bear" if total_ret < -ret_threshold_pct else "sideways")
        )

    return MarketRegime(
        label=label, total_return_pct=round(total_ret, 4), volatility_pct=round(ann_vol_pct, 4)
    )


def regime_coverage_check(
    regimes: list[MarketRegime],
) -> dict[str, Any]:
    """Check how many distinct market conditions are covered.

    Returns
    -------
    {
        "regimes_covered": set of labels,
        "count": number of distinct regimes,
        "passed": True if >= 2 distinct regimes,
        "warning": message if failed,
    }
    """
    distinct = set(r.label for r in regimes)
    passed = len(distinct) >= 2
    out: dict[str, Any] = {
        "regimes_covered": sorted(distinct),
        "count": len(distinct),
        "regime_details": {
            r.label: {"return_pct": r.total_return_pct, "vol_pct": r.volatility_pct}
            for r in regimes
        },
        "passed": passed,
    }
    if not passed:
        out["warning"] = (
            f"Only {len(distinct)} market regime(s) covered: {sorted(distinct)}. "
            "Backtest should span at least 2 of: bull, bear, sideways."
        )
    return out


@dataclass
class SampleSizeCheck:
    total_bars: int
    trade_count: int
    min_bars_ok: bool
    min_trades_ok: bool
    passed: bool
    warning: str | None = None

    # Heuristics from quant literature
    _MIN_BARS: int = 100
    _MIN_TRADES: int = 30


def validate_sample_size(total_bars: int, trade_count: int) -> SampleSizeCheck:
    """Check whether the backtest has enough observations.

    - At least 100 bars of data
    - At least 30 trades for statistical significance
    """
    bars_ok = total_bars >= SampleSizeCheck._MIN_BARS
    trades_ok = trade_count >= SampleSizeCheck._MIN_TRADES
    passed = bars_ok and trades_ok
    warnings: list[str] = []
    if not bars_ok:
        warnings.append(
            f"Only {total_bars} bars (recommend >= {SampleSizeCheck._MIN_BARS}). "
            "Short samples inflate Sharpe and hide path-dependence."
        )
    if not trades_ok:
        warnings.append(
            f"Only {trade_count} trades (recommend >= {SampleSizeCheck._MIN_TRADES}). "
            "Too few trades for statistical significance."
        )
    return SampleSizeCheck(
        total_bars=total_bars,
        trade_count=trade_count,
        min_bars_ok=bars_ok,
        min_trades_ok=trades_ok,
        passed=passed,
        warning=warnings[0] if warnings else None,
    )


@dataclass
class ProfitLossCheck:
    profit_factor: float | None
    passed: bool
    threshold: float = 1.3
    warning: str | None = None


def check_profit_loss_ratio(profit_factor: float | None) -> ProfitLossCheck:
    """Check profit factor >= 1.3 (survive fees + slippage).

    Returns ``passed=True`` when profit_factor is None (no trades → cannot fail).
    """
    if profit_factor is None or profit_factor == 999.0:
        return ProfitLossCheck(
            profit_factor=profit_factor,
            passed=True,
            warning="No losing trades (profit factor extreme) — check sample size.",
        )
    passed = profit_factor >= 1.3
    warning = None
    if not passed:
        warning = (
            f"Profit factor {profit_factor:.2f} < 1.3. "
            "Strategy may not survive fees and slippage after deployment."
        )
    return ProfitLossCheck(profit_factor=profit_factor, passed=passed, warning=warning)


EXIT_REASON_HEALTHY_MAP: dict[str, float] = {
    "take_profit": 0.20,
    "stop_loss": 0.15,
    "signal": 0.40,
    "end_of_backtest": 0.15,
    "liquidation": 0.05,
    "timeout": 0.05,
}


@dataclass
class ExitReasonCheck:
    distribution: dict[str, int]
    pct_distribution: dict[str, float]
    passed: bool
    warning: str | None = None


def check_exit_reason_distribution(trades: list[dict[str, Any]]) -> ExitReasonCheck:
    """Score exit reason distribution against a healthy reference mix.

    Uses ``EXIT_REASON_HEALTHY_MAP`` as the ideal distribution. Deviation
    is measured via Manhattan distance; scores ≥ 0.50 pass.
    """
    dist: dict[str, int] = {}
    for t in trades:
        reason = str(t.get("exit_reason", "unknown"))
        dist[reason] = dist.get(reason, 0) + 1

    total = sum(dist.values())
    pct = {k: (v / total * 100.0) if total else 0.0 for k, v in dist.items()}
    pct_r = {k: round(v, 2) for k, v in pct.items()}

    warnings: list[str] = []
    passed = True

    # 1. Liquidation hard cap
    liq_pct = pct.get("liquidation", 0.0)
    if liq_pct > 15.0:
        warnings.append(f"Liquidation rate {liq_pct:.1f}% > 15% — excessive risk taking.")
        passed = False

    # 2. Score against healthy reference map using Manhattan distance
    healthy = EXIT_REASON_HEALTHY_MAP.copy()
    # Normalise healthy map to percentages matching our pct dict
    healthy_pct = {k: v * 100.0 for k, v in healthy.items()}

    # Build full distribution including zero-entries for healthy reasons not seen
    all_reasons = set(list(healthy_pct.keys()) + list(pct.keys()))
    distance = 0.0
    for reason in all_reasons:
        actual = pct.get(reason, 0.0)
        ideal = healthy_pct.get(reason, 0.0)
        distance += abs(actual - ideal)

    # Score: 1.0 - (distance / 200) — perfect is 1.0, complete mismatch is 0.0
    max_possible_distance = sum(healthy_pct.values()) * 2  # 200
    score = max(0.0, 1.0 - (distance / max_possible_distance))

    if score < 0.50 and total >= 10:
        warnings.append(
            f"Exit reason health score {score:.2f} < 0.50 (target mix: TP≈20%% SL≈15%% "
            f"signal≈40%% timeout≈15%% liq<5%%). Distribution: {pct_r}"
        )
        passed = False
    elif score < 0.30 and total >= 4:
        warnings.append(
            f"Exit reason health score {score:.2f} — severely skewed distribution: {pct_r}"
        )
        passed = False

    # 3. Check for excessive concentration in a single reason
    for reason, p in pct.items():
        if p > 70.0 and reason != "end_of_backtest":
            warnings.append(
                f"Exit reason '{reason}' accounts for {p:.1f}% of trades — "
                "strategy may have no exit diversity."
            )
            passed = False

    return ExitReasonCheck(
        distribution=dist,
        pct_distribution=pct_r,
        passed=passed,
        warning=warnings[0] if warnings else None,
    )


@dataclass
class ForwardValidationResult:
    in_sample_bars: int
    out_of_sample_bars: int
    in_sample_return_pct: float
    out_of_sample_return_pct: float
    in_sample_sharpe: float
    out_of_sample_sharpe: float
    passed: bool
    warning: str | None = None


def split_forward_validation(
    bars_by_symbol: dict[str, list[list[float]]],
    oos_bars: int = 30,
) -> tuple[dict[str, list[list[float]]], dict[str, list[list[float]]]]:
    """Split bars into in-sample (older) and out-of-sample (recent ``oos_bars``).

    Uses the first symbol's bar count as the reference; all symbols are aligned.
    """
    syms = sorted(bars_by_symbol.keys())
    if not syms:
        return {}, {}

    n = len(bars_by_symbol[syms[0]])
    split = max(1, n - oos_bars)

    is_bars: dict[str, list[list[float]]] = {}
    oos_bars_d: dict[str, list[list[float]]] = {}
    for sym in syms:
        rows = bars_by_symbol[sym]
        is_bars[sym] = list(rows[:split])
        oos_bars_d[sym] = list(rows[split:])

    return is_bars, oos_bars_d


@dataclass
class BacktestQualityReport:
    regime_check: dict[str, Any]
    sample_size: SampleSizeCheck
    profit_loss: ProfitLossCheck
    exit_reasons: ExitReasonCheck | None
    forward_validation: ForwardValidationResult | None
    overall_passed: bool
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime_coverage": self.regime_check,
            "sample_size": {
                "total_bars": self.sample_size.total_bars,
                "trade_count": self.sample_size.trade_count,
                "min_bars_ok": self.sample_size.min_bars_ok,
                "min_trades_ok": self.sample_size.min_trades_ok,
                "passed": self.sample_size.passed,
                "warning": self.sample_size.warning,
            },
            "profit_loss_ratio": {
                "profit_factor": self.profit_loss.profit_factor,
                "threshold": self.profit_loss.threshold,
                "passed": self.profit_loss.passed,
                "warning": self.profit_loss.warning,
            },
            "exit_reasons": {
                "distribution": self.exit_reasons.distribution if self.exit_reasons else None,
                "pct_distribution": self.exit_reasons.pct_distribution
                if self.exit_reasons
                else None,
                "passed": self.exit_reasons.passed if self.exit_reasons else None,
                "warning": self.exit_reasons.warning if self.exit_reasons else None,
            }
            if self.exit_reasons
            else None,
            "forward_validation": {
                "in_sample_bars": self.forward_validation.in_sample_bars,
                "out_of_sample_bars": self.forward_validation.out_of_sample_bars,
                "in_sample_return_pct": self.forward_validation.in_sample_return_pct,
                "out_of_sample_return_pct": self.forward_validation.out_of_sample_return_pct,
                "in_sample_sharpe": self.forward_validation.in_sample_sharpe,
                "out_of_sample_sharpe": self.forward_validation.out_of_sample_sharpe,
                "passed": self.forward_validation.passed,
                "warning": self.forward_validation.warning,
            }
            if self.forward_validation
            else None,
            "overall_passed": self.overall_passed,
            "warnings": self.warnings,
        }


def _segment_regimes(
    close_prices: Sequence[float],
    *,
    min_segments: int = 3,
    max_segments: int = 6,
) -> list[MarketRegime]:
    """Split the price series into segments and classify each.

    For short series (< 60 bars) the full window is used as a single
    regime detection chunk.  Longer series are split so the suite can
    aggregate across windows via ``regime_coverage_check``.
    """
    xs = [float(x) for x in close_prices if x > 0]
    n = len(xs)
    if n < 20:
        return [detect_market_regime(xs)]

    # Short window (< 60 bars) — run regime detection on the full series;
    # this prevents false separation that would produce fake "sideways" segments.
    if n < 60:
        return [detect_market_regime(xs)]

    # Aim for segments of roughly 30-50 bars each
    ideal_seg_size = max(10, min(50, n // min_segments))
    n_segments = max(min_segments, min(max_segments, n // ideal_seg_size))
    seg_size = max(10, n // n_segments)

    regimes: list[MarketRegime] = []
    for i in range(n_segments):
        start = i * seg_size
        end = min((i + 1) * seg_size, n)
        chunk = xs[start:end]
        if len(chunk) >= 10:
            regimes.append(detect_market_regime(chunk))
    return regimes if regimes else [detect_market_regime(xs)]


def generate_quality_report(
    *,
    close_prices: Sequence[float],
    total_bars: int,
    trade_count: int,
    profit_factor: float | None,
    trades: list[dict[str, Any]] | None = None,
    forward_result: ForwardValidationResult | None = None,
) -> BacktestQualityReport:
    """Run quality checks and return a report."""
    regime_result = regime_coverage_check(_segment_regimes(close_prices))
    ss = validate_sample_size(total_bars, trade_count)
    pl = check_profit_loss_ratio(profit_factor)
    exit_check = check_exit_reason_distribution(trades) if trades else None
    fwd = forward_result

    warnings: list[str] = []
    for ck in [ss, pl, exit_check, fwd]:
        if ck is None:
            continue
        w = getattr(ck, "warning", None)
        if w:
            warnings.append(w)
    if not regime_result.get("passed", True):
        warnings.append(str(regime_result.get("warning", "")))

    checks = [ss.passed, pl.passed]
    if exit_check is not None:
        checks.append(exit_check.passed)
    if fwd is not None:
        checks.append(fwd.passed)
    checks.append(regime_result.get("passed", True))
    overall_passed = all(checks)

    return BacktestQualityReport(
        regime_check=regime_result,
        sample_size=ss,
        profit_loss=pl,
        exit_reasons=exit_check,
        forward_validation=fwd,
        overall_passed=overall_passed,
        warnings=warnings,
    )
