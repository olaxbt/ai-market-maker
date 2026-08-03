"""LLM environment helpers for OpenAI-compatible providers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Sequence

ATLAS_CLOUD_BASE_URL = "https://api.atlascloud.ai/v1"
ATLAS_CLOUD_MODEL = "deepseek-ai/deepseek-v4-pro"
_ATLAS_KEY_NAMES = ("ATLASCLOUD_API_KEY", "ATLAS_CLOUD_API_KEY")
_ATLAS_BASE_URL_NAMES = (
    "ATLASCLOUD_BASE_URL",
    "ATLAS_CLOUD_BASE_URL",
    "ATLASCLOUD_API_BASE",
    "ATLAS_CLOUD_API_BASE",
)
_ATLAS_MODEL_NAMES = ("ATLASCLOUD_MODEL", "ATLAS_CLOUD_MODEL")


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str | None
    model: str


def _first(env: Mapping[str, str], names: Sequence[str]) -> str:
    for name in names:
        value = (env.get(name) or "").strip()
        if value:
            return value
    return ""


def resolve_llm_config(
    env: Mapping[str, str] | None = None,
    *,
    key_names: Sequence[str] = ("OPENAI_API_KEY", "LLM_API_KEY"),
    base_url_names: Sequence[str] = ("OPENAI_BASE_URL",),
    model_names: Sequence[str] = ("OPENAI_MODEL",),
    default_base_url: str | None = None,
    default_model: str = "gpt-4o-mini",
) -> LLMConfig:
    """Resolve existing provider settings, then Atlas Cloud aliases.

    Existing provider variables keep priority. Atlas Cloud defaults are only
    selected when none of the caller's existing key variables are configured.
    """
    env_map = os.environ if env is None else env
    api_key = _first(env_map, key_names)
    if api_key:
        return LLMConfig(
            api_key=api_key,
            base_url=_first(env_map, base_url_names) or default_base_url,
            model=_first(env_map, model_names) or default_model,
        )

    atlas_key = _first(env_map, _ATLAS_KEY_NAMES)
    if atlas_key:
        return LLMConfig(
            api_key=atlas_key,
            base_url=_first(env_map, _ATLAS_BASE_URL_NAMES) or ATLAS_CLOUD_BASE_URL,
            model=_first(env_map, _ATLAS_MODEL_NAMES) or ATLAS_CLOUD_MODEL,
        )

    return LLMConfig(
        api_key="",
        base_url=_first(env_map, base_url_names) or default_base_url,
        model=_first(env_map, model_names) or default_model,
    )


def _read_key(env: Mapping[str, str] | None) -> str:
    """Return the first non-empty API key from *env*."""
    return resolve_llm_config(env).api_key


def llm_key_available(env: Mapping[str, str] | None = None) -> bool:
    """Return True when an LLM API key is configured in *env*."""
    return bool(_read_key(env))


def use_llm_arbitrator(env: Mapping[str, str] | None = None) -> bool:
    """Return True when an LLM provider key is configured.

    Legacy ``AI_MARKET_MAKER_USE_LLM=0`` forces False.
    """
    if env is None:
        env = os.environ

    old_flag = (env.get("AI_MARKET_MAKER_USE_LLM") or "").strip().lower()
    if old_flag in ("0", "false", "no", "off"):
        return False

    return bool(_read_key(env))


def require_llm_key(env: Mapping[str, str] | None = None) -> None:
    """Exit with a clear message if no LLM key is configured."""
    m = os.environ if env is None else env
    if (m.get("PYTEST_CURRENT_TEST") or "").strip():
        return
    if not llm_key_available(env):
        print(
            "FATAL: an LLM API key is required. "
            "Set OPENAI_API_KEY or ATLASCLOUD_API_KEY in your environment or .env file.",
            file=__import__("sys").stderr,
        )
        __import__("sys").exit(1)


__all__ = [
    "ATLAS_CLOUD_BASE_URL",
    "ATLAS_CLOUD_MODEL",
    "LLMConfig",
    "llm_key_available",
    "require_llm_key",
    "resolve_llm_config",
    "use_llm_arbitrator",
]
