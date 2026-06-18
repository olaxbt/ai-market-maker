"""LLM env helpers for arbitrator key detection and legacy flags."""

from __future__ import annotations

import os


def _read_key(env: dict[str, str] | None) -> str:
    """Return the first non-empty API key from *env*."""
    if env is None:
        env = os.environ
    return (env.get("OPENAI_API_KEY") or env.get("LLM_API_KEY") or "").strip()


def llm_key_available(env: dict[str, str] | None = None) -> bool:
    """Return True when an LLM API key is configured in *env*."""
    return bool(_read_key(env))


def use_llm_arbitrator(env: dict[str, str] | None = None) -> bool:
    """Return True when an LLM provider key is configured.

    Legacy ``AI_MARKET_MAKER_USE_LLM=0`` forces False.
    """
    if env is None:
        env = os.environ

    old_flag = (env.get("AI_MARKET_MAKER_USE_LLM") or "").strip().lower()
    if old_flag in ("0", "false", "no", "off"):
        return False

    return bool(_read_key(env))


def require_llm_key(env: dict[str, str] | None = None) -> None:
    """Exit with a clear message if no LLM key is configured."""
    if not llm_key_available(env):
        print(
            "FATAL: OPENAI_API_KEY is required. "
            "Set OPENAI_API_KEY in your environment or .env file.",
            file=__import__("sys").stderr,
        )
        __import__("sys").exit(1)


__all__ = ["llm_key_available", "require_llm_key", "use_llm_arbitrator"]
