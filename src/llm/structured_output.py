"""Shared helpers for enforcing structured LLM outputs.

This project runs multiple LLM-driven nodes that must produce machine-usable JSON.
Rather than relying on "best effort" parsing alone, we enforce:

- strict "JSON only" instructions (portable across OpenAI-compatible providers)
- validation + bounded retries (prevents silent degradation to defaults)

These helpers are intentionally lightweight (no extra dependencies).
"""

from __future__ import annotations

import os
from typing import Iterable

from config.app_settings import load_app_settings


def _app_llm_defaults() -> tuple[bool, int]:
    """Return (strict_json, output_retries) from app settings, with safe fallbacks."""

    try:
        s = load_app_settings()
        return bool(s.llm.strict_json), int(s.llm.output_retries)
    except Exception:
        return True, 2


def env_int(name: str, default: int) -> int:
    """Parse an int env var with a safe default."""

    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def env_bool(name: str, default: bool) -> bool:
    """Parse a boolean env var with a safe default."""

    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "y", "on")


def clamp_int(v: int, *, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def strict_json_suffix(
    *,
    keys: Iterable[str],
    extra_rules: Iterable[str] = (),
) -> str:
    """Build a strict, provider-agnostic JSON-only instruction suffix."""

    keys_s = ", ".join(keys)
    rules = [
        "STRICT OUTPUT REQUIREMENTS:",
        "- Output ONLY a single JSON object.",
        "- Do NOT wrap in markdown fences.",
        "- Do NOT include any commentary before/after.",
        f"- Keys MUST be exactly: {keys_s}.",
        *list(extra_rules),
    ]
    return "\n\n" + "\n".join(rules) + "\n"


def llm_output_retries() -> int:
    """Preferred default retries for LLM structured outputs.

    Config-first: read from `config/app.default.json` → `llm.output_retries`.
    Env override (optional): `AIMM_LLM_OUTPUT_RETRIES`.
    """

    strict_default, retries_default = _app_llm_defaults()
    _ = strict_default
    return env_int("AIMM_LLM_OUTPUT_RETRIES", retries_default)


def llm_strict_json_enabled() -> bool:
    """Preferred default strict-json toggle for LLM structured outputs.

    Config-first: read from `config/app.default.json` → `llm.strict_json`.
    Env override (optional): `AIMM_LLM_STRICT_JSON`.
    """

    strict_default, _retries_default = _app_llm_defaults()
    return env_bool("AIMM_LLM_STRICT_JSON", strict_default)
