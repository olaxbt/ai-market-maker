"""Tier-1 Strategy Blueprint (Architect) + deterministic Applier engine."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from tier1.applier import apply_strategy, load_blueprint_path
from tier1.metric_catalog import all_tier1_metrics, metric_ids_sorted
from tier1.models import ExecutionPayload, PortfolioDeskBridge, StrategyBlueprint
from tier1.presets import get_preset, list_presets
from tier1.validate import (
    iter_blueprint_warnings,
    log_blueprint_warnings,
    strict_validate_blueprint_weights,
)

__all__ = [
    "ExecutionPayload",
    "PortfolioDeskBridge",
    "StrategyBlueprint",
    "effective_portfolio_desk_bridge",
    "all_tier1_metrics",
    "apply_strategy",
    "get_preset",
    "iter_blueprint_warnings",
    "list_presets",
    "load_blueprint_path",
    "load_tier1_blueprint_from_env",
    "log_blueprint_warnings",
    "metric_ids_sorted",
    "strict_validate_blueprint_weights",
]


def load_tier1_blueprint_from_env() -> StrategyBlueprint | None:
    """Load blueprint from ``AIMM_STRATEGY_BLUEPRINT_PATH`` or ``AIMM_STRATEGY_PRESET``."""
    logger = logging.getLogger(__name__)
    path = (os.environ.get("AIMM_STRATEGY_BLUEPRINT_PATH") or "").strip()
    if path:
        p = Path(path)
        if p.is_file():
            return load_blueprint_path(p)
        logger.warning("AIMM_STRATEGY_BLUEPRINT_PATH is not a file: %s", path)
    preset = (os.environ.get("AIMM_STRATEGY_PRESET") or "").strip().lower()
    if not preset or preset in ("none", "off", "0", "false"):
        return None
    try:
        return get_preset(preset)
    except KeyError:
        logger.warning("Unknown AIMM_STRATEGY_PRESET=%r; valid: %s", preset, list_presets())
        return None


def effective_portfolio_desk_bridge() -> PortfolioDeskBridge:
    """``Tactical_Parameters.Portfolio_Desk_Bridge`` from the active Tier-1 blueprint, or defaults (all off)."""
    bp = load_tier1_blueprint_from_env()
    if bp is None:
        return PortfolioDeskBridge()
    return bp.tactical_parameters.portfolio_desk_bridge
