"""Execution mode for the trading workflow (backtest, paper, live).

Live mode is gated behind an explicit environment flag to avoid accidental production use.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Mapping

MODE_ENV = "MODE"
LIVE_CONFIRM_ENV = "AI_MARKET_MAKER_ALLOW_LIVE"


class RunMode(StrEnum):
    """Execution mode; matches ``HedgeFundState.run_mode`` and ``docs/run-modes.md``."""

    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


def load_run_mode(
    *,
    env: Mapping[str, str] | None = None,
    override: str | None = None,
) -> RunMode:
    """
    Resolve run mode from ``override`` (e.g. CLI), else ``MODE`` env, default ``paper``.

    Raises:
        ValueError: If ``live`` is requested without ``AI_MARKET_MAKER_ALLOW_LIVE=1``.
    """
    raw = (override or "").strip().lower() if override else ""
    if not raw:
        env_map = env if env is not None else os.environ
        raw = (env_map.get(MODE_ENV) or RunMode.PAPER.value).strip().lower()

    try:
        mode = RunMode(raw)
    except ValueError as e:
        allowed = ", ".join(m.value for m in RunMode)
        raise ValueError(f"Invalid run mode {raw!r}. Use one of: {allowed}") from e

    if mode is RunMode.LIVE:
        env_map = env if env is not None else os.environ
        if env_map.get(LIVE_CONFIRM_ENV) not in ("1", "true", "yes"):
            raise ValueError(
                f"Run mode {RunMode.LIVE.value!r} requires {LIVE_CONFIRM_ENV}=1 "
                "(or true/yes). See docs/run-modes.md."
            )

    return mode


__all__ = ["LIVE_CONFIRM_ENV", "MODE_ENV", "RunMode", "load_run_mode"]
