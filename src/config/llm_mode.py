"""Toggle portfolio/desk LLM nodes via ``AIMM_LLM_MODE``."""

from __future__ import annotations

import os
from typing import Mapping

_ENV = "AIMM_LLM_MODE"
_REQUIRED_ENV = "AIMM_LLM_REQUIRED"
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


def llm_required(env: Mapping[str, str] | None = None) -> bool:
    """Return True when ``AIMM_LLM_REQUIRED`` is set to a truthy value.

    When ``llm_required()`` is True, callers should refuse to start
    unless ``llm_key_available()`` also returns True (see
    ``config.llm_env.require_llm_key``).
    """
    m = env if env is not None else os.environ
    raw = (m.get(_REQUIRED_ENV) or "").strip().lower()
    return raw in _ON


__all__ = ["llm_mode_enabled", "llm_required"]
