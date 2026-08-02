"""Seconds between full LangGraph runs in long-running stacks."""

from __future__ import annotations

import os
import sys
import warnings
from typing import Mapping

from config.llm_env import use_llm_arbitrator

STRATEGY_INTERVAL_ENV = "STRATEGY_INTERVAL_SEC"
DEFAULT_STRATEGY_INTERVAL_SEC = 900

LLM_SANE_MIN_INTERVAL_SEC = 300

_MIN_INTERVAL_SEC = 300
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
    env_map = env if env is not None else os.environ
    use_llm = use_llm_arbitrator(env_map)
    if use_llm and interval_sec < LLM_SANE_MIN_INTERVAL_SEC:
        print(
            f"[cadence] LLM key configured with {STRATEGY_INTERVAL_ENV}={interval_sec}s "
            f"(<{LLM_SANE_MIN_INTERVAL_SEC}s): full graph each tick — high token use.",
            file=sys.stderr,
        )


__all__ = [
    "DEFAULT_STRATEGY_INTERVAL_SEC",
    "LLM_SANE_MIN_INTERVAL_SEC",
    "STRATEGY_INTERVAL_ENV",
    "load_strategy_interval_sec",
    "warn_if_aggressive_cadence",
]
