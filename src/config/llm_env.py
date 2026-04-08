"""Single definition of when the Tier-2 **LLM signal arbitrator** is enabled.

Confusion often comes from treating ``0``/``1`` as vague toggles. Here:

- **OFF** (default): empty, ``0``, ``false``, ``no``, or anything else unrecognized.
- **ON**: ``1``, ``true``, ``yes``, ``y``, ``on`` (case-insensitive).

When ON, :func:`main.build_workflow` wires ``signal_arbitrator_llm`` instead of the
deterministic ``signal_arbitrator``, and each graph tick may call the model (costly).
"""

from __future__ import annotations

import os
from typing import Mapping

_ENV_NAME = "AI_MARKET_MAKER_USE_LLM"

_ON_VALUES = frozenset({"1", "true", "yes", "y", "on"})
_OFF_VALUES = frozenset({"0", "false", "no", "n", "off"})


def use_llm_arbitrator(env: Mapping[str, str] | None = None) -> bool:
    """Return True if the LLM-backed signal arbitrator should be used."""
    m = env if env is not None else os.environ
    v = (m.get(_ENV_NAME) or "").strip().lower()
    if v in _ON_VALUES:
        return True
    if v in _OFF_VALUES:
        return False
    # Auto mode: enable when a key exists (but never during pytest to avoid accidental paid calls).
    if (m.get("PYTEST_CURRENT_TEST") or "").strip():
        return False
    return bool((m.get("OPENAI_API_KEY") or "").strip())


__all__ = ["use_llm_arbitrator"]
