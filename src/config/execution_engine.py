"""Execution engine selection.

AI_MARKET_MAKER_EXECUTION_ENGINE=legacy  (default) — existing NexusAdapter paper path, unchanged
AI_MARKET_MAKER_EXECUTION_ENGINE=oms     — route through OMS lifecycle tracking (opt-in)

No live exchange calls are made in either mode unless EXCHANGE and AI_MARKET_MAKER_ALLOW_LIVE
are both set explicitly.
"""

from __future__ import annotations

import os
from enum import StrEnum
from typing import Mapping

EXECUTION_ENGINE_ENV = "AI_MARKET_MAKER_EXECUTION_ENGINE"


class ExecutionEngine(StrEnum):
    LEGACY = "legacy"
    OMS = "oms"


def load_execution_engine(*, env: Mapping[str, str] | None = None) -> ExecutionEngine:
    """Return the configured execution engine. Unknown values fall back to LEGACY."""
    e = env if env is not None else os.environ
    raw = (e.get(EXECUTION_ENGINE_ENV) or "legacy").strip().lower()
    if raw == "oms":
        return ExecutionEngine.OMS
    return ExecutionEngine.LEGACY


__all__ = ["EXECUTION_ENGINE_ENV", "ExecutionEngine", "load_execution_engine"]
