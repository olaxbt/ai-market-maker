"""LLM key availability helpers."""

from __future__ import annotations

import os


def llm_key_available() -> bool:
    """Return True if an LLM API key is available.

    Checks ``OPENAI_API_KEY`` (or ``LLM_API_KEY`` as fallback).
    """
    return bool((os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip())


def require_llm_key() -> None:
    """Exit with a clear message if no LLM key is set."""
    if not llm_key_available():
        print(
            "FATAL: OPENAI_API_KEY is required. "
            "Set OPENAI_API_KEY in your environment or .env file.",
            file=__import__("sys").stderr,
        )
        __import__("sys").exit(1)


__all__ = ["llm_key_available", "require_llm_key"]
