"""Per-agent LLM toggle for weighted_convergence vs agent_llm run modes."""

from __future__ import annotations

import os
from typing import Mapping

_ENV_MODE = "AIMM_RUN_MODE"
_AGENT_LLM_MODE = "agent_llm"
_WEIGHTED_CONVERGENCE = "weighted_convergence"

# AIMM_LLM_AGENTS=2.1,2.3 or ALL
_ENV_AGENTS = "AIMM_LLM_AGENTS"
_ALL_SENTINEL = "ALL"


def current_run_mode(env: Mapping[str, str] | None = None) -> str:
    """Return the current execution mode string.

    Returns "weighted_convergence" or "agent_llm".
    Default is "weighted_convergence" (zero LLM calls).
    """
    m = env if env is not None else os.environ
    raw = (m.get(_ENV_MODE) or _WEIGHTED_CONVERGENCE).strip().lower()
    return raw if raw in (_AGENT_LLM_MODE, _WEIGHTED_CONVERGENCE) else _WEIGHTED_CONVERGENCE


def is_agent_llm_mode(env: Mapping[str, str] | None = None) -> bool:
    """True when global mode is 'agent_llm'."""
    return current_run_mode(env) == _AGENT_LLM_MODE


def llm_enabled_agents(env: Mapping[str, str] | None = None) -> frozenset[str]:
    """Return the set of agent IDs that should use LLM path.

    When AIMM_LLM_AGENTS=ALL, every agent is included.
    """
    m = env if env is not None else os.environ
    raw = (m.get(_ENV_AGENTS) or "").strip()
    if not raw:
        return frozenset()
    if raw.upper() == _ALL_SENTINEL:
        return frozenset({"*"})
    return frozenset(a.strip() for a in raw.split(",") if a.strip())


def agent_llm_enabled(agent_id: str, env: Mapping[str, str] | None = None) -> bool:
    """Check if a specific agent should use LLM path.

    Returns False when global mode is not 'agent_llm'.
    When AIMM_LLM_AGENTS=ALL, all agents are enabled.
    When AIMM_LLM_AGENTS=2.1,2.3, only those agents use LLM.
    """
    if not is_agent_llm_mode(env):
        return False
    enabled = llm_enabled_agents(env)
    if not enabled:
        return False
    if _ALL_SENTINEL.lower() in enabled or "*" in enabled:
        return True
    return agent_id in enabled


def describe_mode(env: Mapping[str, str] | None = None) -> dict:
    """Return a diagnostic dict of the current LLM mode configuration."""
    mode = current_run_mode(env)
    enabled = llm_enabled_agents(env)
    return {
        "mode": mode,
        "agent_llm_enabled": is_agent_llm_mode(env),
        "llm_agents": sorted(enabled) if enabled else [],
        "all_agents_llm": _ALL_SENTINEL.lower() in enabled or "*" in enabled,
    }


__all__ = [
    "agent_llm_enabled",
    "current_run_mode",
    "describe_mode",
    "is_agent_llm_mode",
    "llm_enabled_agents",
]
