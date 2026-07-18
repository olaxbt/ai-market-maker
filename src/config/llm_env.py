"""LLM key checks — agentic runs require a configured provider key."""

from __future__ import annotations

import os
import sys
from typing import Mapping


def _read_key(env: Mapping[str, str]) -> str:
    return (env.get("OPENAI_API_KEY") or env.get("LLM_API_KEY") or "").strip()


def llm_key_available(env: Mapping[str, str] | None = None) -> bool:
    """Return True when an LLM API key is configured."""
    m = os.environ if env is None else env
    return bool(_read_key(m))


def use_llm_arbitrator(env: Mapping[str, str] | None = None) -> bool:
    """True when a provider key is present (agentic default)."""
    return llm_key_available(env)


def require_llm_key(env: Mapping[str, str] | None = None) -> None:
    """Exit unless an LLM API key is configured (skipped under pytest)."""
    m = os.environ if env is None else env
    if (m.get("PYTEST_CURRENT_TEST") or "").strip():
        return
    if llm_key_available(m):
        return
    print(
        "FATAL: OPENAI_API_KEY (or LLM_API_KEY) is required for agentic trading. "
        "Set a provider key in your environment or .env file.",
        file=sys.stderr,
    )
    sys.exit(1)


__all__ = ["llm_key_available", "require_llm_key", "use_llm_arbitrator"]
