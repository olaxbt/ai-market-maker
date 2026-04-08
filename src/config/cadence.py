"""Decision loop timing: how often the full graph runs in long-running / dev stacks.

The **full LangGraph** run (Tier-1 desks + optional LLM arbitrator + risk + execution)
is expensive in tokens and API calls. Use a conservative default and override only when you need
fast feedback (e.g. integration testing).
"""

from __future__ import annotations

import os
import sys
import warnings
from typing import Mapping

from config.llm_env import use_llm_arbitrator

STRATEGY_INTERVAL_ENV = "STRATEGY_INTERVAL_SEC"
# Default ~3 minutes: aligns with common “desk refresh” loops and limits token burn.
DEFAULT_STRATEGY_INTERVAL_SEC = 180

# If LLM is enabled, intervals shorter than this are unusual for production-shaped runs.
LLM_SANE_MIN_INTERVAL_SEC = 120

_MIN_INTERVAL_SEC = 1
_MAX_INTERVAL_SEC = 86400


def load_strategy_interval_sec(
    *,
    env: Mapping[str, str] | None = None,
) -> int:
    """
    Parse ``STRATEGY_INTERVAL_SEC`` (seconds between strategy loop iterations).

    Returns a clamped integer in ``[1, 86400]``. Invalid values fall back to the default.
    """
    env_map = env if env is not None else os.environ
    raw = (env_map.get(STRATEGY_INTERVAL_ENV) or "").strip()
    if not raw:
        return DEFAULT_STRATEGY_INTERVAL_SEC
    try:
        n = int(raw, 10)
    except ValueError:
        warnings.warn(
            f"{STRATEGY_INTERVAL_ENV}={raw!r} is not a valid integer; "
            f"using default {DEFAULT_STRATEGY_INTERVAL_SEC}s",
            stacklevel=2,
        )
        return DEFAULT_STRATEGY_INTERVAL_SEC
    if n < _MIN_INTERVAL_SEC or n > _MAX_INTERVAL_SEC:
        warnings.warn(
            f"{STRATEGY_INTERVAL_ENV}={n} outside [{_MIN_INTERVAL_SEC}, {_MAX_INTERVAL_SEC}]; "
            f"clamping",
            stacklevel=2,
        )
    return max(_MIN_INTERVAL_SEC, min(_MAX_INTERVAL_SEC, n))


def warn_if_aggressive_cadence(interval_sec: int, *, env: Mapping[str, str] | None = None) -> None:
    """Emit a stderr hint when LLM is on but the loop is faster than a typical desk cycle."""
    env_map = env if env is not None else os.environ
    use_llm = use_llm_arbitrator(env_map)
    if use_llm and interval_sec < LLM_SANE_MIN_INTERVAL_SEC:
        print(
            f"[cadence] AI_MARKET_MAKER_USE_LLM=1 with {STRATEGY_INTERVAL_ENV}={interval_sec}s "
            f"(<{LLM_SANE_MIN_INTERVAL_SEC}s): each tick runs the full graph and LLM calls — "
            "expect high token usage. Consider >=180s for demos, or disable LLM for fast ticks.",
            file=sys.stderr,
        )


__all__ = [
    "DEFAULT_STRATEGY_INTERVAL_SEC",
    "LLM_SANE_MIN_INTERVAL_SEC",
    "STRATEGY_INTERVAL_ENV",
    "load_strategy_interval_sec",
    "warn_if_aggressive_cadence",
]
