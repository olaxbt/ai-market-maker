"""Default agentic desk combo for backtests when no deploy.active.json is present."""

from __future__ import annotations

import copy
from typing import Any

# macro_tilt preset (run_agentic_sweep): TA-led desk + macro/pattern support.
DEFAULT_AGENTIC_PROFILE_ID = "macro_tilt"
DEFAULT_AGENTIC_PROFILE_WEIGHTS: dict[str, float] = {
    "2.3": 0.55,
    "2.1": 0.15,
    "1.1": 0.25,
}

# Mirrors weighted_arbitrator._V4_DECISION_THRESHOLD / sweep _THR_BASE.
DEFAULT_AGENTIC_DECISION_THRESHOLD: dict[str, Any] = {
    "buy": {"min_composite": 53, "min_confidence": 16},
    "sell": {"max_composite": 41, "min_confidence": 26},
    "hold": {"else": True},
    "alignment_gating": {
        "enabled": True,
        "min_factors_for_directional": 2,
        "risk_override_if_blocked": True,
    },
    "ta_led": {
        "enabled": True,
        "agent_id": "2.3",
        "buy_min_composite": 57,
        "sell_max_composite": 43,
        "min_confidence": 14,
    },
}


def default_agentic_profile_weights() -> dict[str, float]:
    return dict(DEFAULT_AGENTIC_PROFILE_WEIGHTS)


def default_agentic_decision_threshold() -> dict[str, Any]:
    return copy.deepcopy(DEFAULT_AGENTIC_DECISION_THRESHOLD)


__all__ = [
    "DEFAULT_AGENTIC_DECISION_THRESHOLD",
    "DEFAULT_AGENTIC_PROFILE_ID",
    "DEFAULT_AGENTIC_PROFILE_WEIGHTS",
    "default_agentic_decision_threshold",
    "default_agentic_profile_weights",
]
