"""Blueprint sanity checks: weight sums, optional strict mode."""

from __future__ import annotations

import logging
import os
from typing import Iterator

from tier1.models import StrategyBlueprint

logger = logging.getLogger(__name__)


def iter_blueprint_warnings(blueprint: StrategyBlueprint) -> Iterator[str]:
    """Non-fatal authoring hints (log in dev / CI)."""
    tactical = blueprint.tactical_parameters
    factors = tactical.multi_factor_alpha_matrix
    if factors:
        s = sum(int(f.weight_pct) for f in factors)
        if s != 100:
            yield (
                f"Multi_Factor_Alpha_Matrix weight_pct sum is {s}, not 100 — "
                "min_convergence_score_required uses the same scale; adjust for clarity or intent."
            )

    mix = blueprint.persona_genetics.persona_signal_mix
    if mix is not None:
        t = (
            mix.trend_weight
            + mix.momentum_weight
            + mix.mean_revert_weight
            + mix.volume_weight
            + mix.volatility_weight
        )
        if t > 0.01 and abs(t - 1.0) > 0.05:
            yield (
                f"Persona_Signal_Mix component weights sum to {t:.4f}; "
                "convention is ~1.0 when any are non-zero."
            )

    ma = blueprint.trade_management_logic.ma_cross_periods
    if ma.enabled and ma.fast_period >= ma.slow_period:
        yield (
            f"MA_Cross_Periods: fast_period ({ma.fast_period}) should be < slow_period ({ma.slow_period})."
        )


def log_blueprint_warnings(blueprint: StrategyBlueprint) -> None:
    for msg in iter_blueprint_warnings(blueprint):
        logger.warning("Tier-1 blueprint: %s", msg)


def strict_validate_blueprint_weights(blueprint: StrategyBlueprint) -> None:
    """Raise if ``AIMM_TIER1_STRICT_WEIGHTS`` is set and alpha weights do not sum to 100."""
    raw = (os.environ.get("AIMM_TIER1_STRICT_WEIGHTS") or "").strip().lower()
    if raw not in ("1", "true", "yes", "on"):
        return
    factors = blueprint.tactical_parameters.multi_factor_alpha_matrix
    if not factors:
        return
    s = sum(int(f.weight_pct) for f in factors)
    if s != 100:
        raise ValueError(
            f"AIMM_TIER1_STRICT_WEIGHTS: Multi_Factor_Alpha_Matrix weights sum to {s}, expected 100."
        )


__all__ = [
    "iter_blueprint_warnings",
    "log_blueprint_warnings",
    "strict_validate_blueprint_weights",
]
