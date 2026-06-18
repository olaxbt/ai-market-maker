"""Per-agent LLM toggle (weighted_convergence vs agent_llm)."""

from __future__ import annotations

import os
from typing import Mapping

# Global mode env
_ENV_MODE = "AIMM_RUN_MODE"
_AGENT_LLM_MODE = "agent_llm"
_WEIGHTED_CONVERGENCE = "weighted_convergence"

# Per-agent toggle env — comma-separated agent IDs
# Example: AIMM_LLM_AGENTS=2.1,2.3,3.1
_ENV_AGENTS = "AIMM_LLM_AGENTS"

# When set to "ALL", every agent uses LLM path
_ALL_SENTINEL = "ALL"


def current_run_mode(env: Mapping[str, str] | None = None) -> str:
    """Return the current execution mode string.

    Returns "weighted_convergence" or "agent_llm".
    Default is "weighted_convergence" (zero LLM calls).
    """
    if env is None:
        env = os.environ
    raw = (env.get(_ENV_MODE) or "").strip().lower()
    if raw in (_AGENT_LLM_MODE, "agentic", "llm"):
        return _AGENT_LLM_MODE
    return _WEIGHTED_CONVERGENCE


def is_agent_llm_mode(env: Mapping[str, str] | None = None) -> bool:
    """Return True if global mode is ``agent_llm``."""
    return current_run_mode(env) == _AGENT_LLM_MODE


def agent_llm_enabled(
    agent_id: str,
    env: Mapping[str, str] | None = None,
    *,
    default: bool = False,
) -> bool:
    """Return True if *agent_id* should use the LLM path.

    Priority:
    1. ``AIMM_LLM_AGENTS`` env var: comma-separated IDs or ``ALL``.
    2. ``default`` parameter (used when nothing is configured).

    In agent_llm mode, a failed LLM call yields an error contract (source: error),
    not the deterministic Tier-0 output.
    """
    if env is None:
        env = os.environ
    raw = (env.get(_ENV_AGENTS) or "").strip()
    if not raw:
        return default
    if raw == _ALL_SENTINEL:
        return True
    agents = [a.strip() for a in raw.split(",") if a.strip()]
    return agent_id in agents
