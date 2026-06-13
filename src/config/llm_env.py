"""LLM key availability and arbitrator mode helpers."""

from __future__ import annotations

import os
from typing import Mapping


def llm_key_available(env: Mapping[str, str] | None = None) -> bool:
    """Return True when an LLM API key is configured."""
    m = env if env is not None else os.environ
    return bool((m.get("OPENAI_API_KEY") or m.get("LLM_API_KEY") or "").strip())


def llm_arbitrator_mode(env: Mapping[str, str] | None = None) -> str:
    """Return ``weighted_convergence`` (default) or ``llm``."""
    m = env if env is not None else os.environ
    raw = (m.get("AIMM_ARBITRATOR_MODE") or "weighted_convergence").strip().lower()
    return "llm" if raw == "llm" else "weighted_convergence"


def require_llm_key() -> None:
    """Exit with a clear message if no LLM key is set."""
    if not llm_key_available():
        print(
            "FATAL: OPENAI_API_KEY is required. "
            "Set OPENAI_API_KEY in your environment or .env file.",
            file=__import__("sys").stderr,
        )
        __import__("sys").exit(1)


__all__ = ["llm_arbitrator_mode", "llm_key_available", "require_llm_key"]
