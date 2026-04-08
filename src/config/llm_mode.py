"""Single switch for 'LLM mode' in the app.

Goal: **agentic by default** when the user configured keys, but **easy onboarding** when they didn't.

Rules:
- If `AIMM_LLM_MODE` is explicitly set:
  - ON values: 1/true/yes/on/y
  - OFF values: 0/false/no/off/n
- Else: enable only when `OPENAI_API_KEY` is present.
"""

from __future__ import annotations

import os
from typing import Mapping

_ENV = "AIMM_LLM_MODE"
_ON = frozenset({"1", "true", "yes", "y", "on"})
_OFF = frozenset({"0", "false", "no", "n", "off"})


def llm_mode_enabled(env: Mapping[str, str] | None = None) -> bool:
    m = env if env is not None else os.environ
    raw = (m.get(_ENV) or "").strip().lower()
    if raw in _ON:
        return True
    if raw in _OFF:
        return False
    # Test safety: never auto-enable in pytest unless explicitly requested.
    if (m.get("PYTEST_CURRENT_TEST") or "").strip():
        return False
    # Auto mode: only on when a key exists.
    return bool((m.get("OPENAI_API_KEY") or "").strip())


__all__ = ["llm_mode_enabled"]
