"""Deploy config loader — runtime integration for deployed configurations.

Reads ``config/deploy.active.json`` (written by the ``POST /deploy-config``
endpoint) and provides a clean interface for the rest of the system to
access deployed policy, execution settings, agent topology, and profile
weights.

Usage::

    from config.deploy_loader import load_deploy_config

    cfg = load_deploy_config()
    if cfg is not None:
        weights = cfg.get("effective_weights", {})
        mode = cfg.get("execution", {}).get("arbitrator_mode", "weighted_convergence")
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_DEPLOY_PATH = "config/deploy.active.json"


def _deploy_path() -> Path:
    override = (os.getenv("AIMM_DEPLOY_CONFIG_PATH") or "").strip()
    return Path(override) if override else Path(_DEFAULT_DEPLOY_PATH)


def load_deploy_config() -> dict[str, Any] | None:
    """Load the active deployed configuration from disk.

    Returns the parsed config dict, or ``None`` if no deploy config exists
    or it cannot be parsed.
    """
    path = _deploy_path()
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            logger.warning("deploy config at %s is not a dict, ignoring", path)
            return None
        return obj
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("failed to read deploy config at %s: %s", path, e)
        return None


def get_effective_weights() -> dict[str, float] | None:
    """Get effective agent weights from the active deploy config.

    Returns ``None`` if no deploy config is active.
    """
    cfg = load_deploy_config()
    if cfg is None:
        return None
    ew = cfg.get("effective_weights")
    if not isinstance(ew, dict):
        return None
    return dict(ew)


def get_arbitrator_mode() -> str | None:
    """Get the arbitrator mode from the active deploy config.

    Returns ``"weighted_convergence"``, ``"agent_llm"``, or ``None`` if
    no deploy config is active.
    """
    cfg = load_deploy_config()
    if cfg is None:
        return None
    return cfg.get("execution", {}).get("arbitrator_mode")


def get_deploy_policy() -> dict[str, Any] | None:
    """Get policy overrides from the active deploy config.

    Returns a dict of policy keys to merge into the base FundPolicy,
    or ``None`` if no deploy config is active.
    """
    cfg = load_deploy_config()
    if cfg is None:
        return None
    return cfg.get("policy")


def get_deploy_agents() -> dict[str, dict[str, Any]] | None:
    """Get the agent topology from the active deploy config.

    Returns a map of agent_id -> agent_config, or ``None``.
    """
    cfg = load_deploy_config()
    if cfg is None:
        return None
    agents = cfg.get("agents")
    if not isinstance(agents, dict):
        return None
    return dict(agents)


def get_deploy_profile_id() -> str | None:
    """Get the profile_id referenced in the active deploy config."""
    cfg = load_deploy_config()
    if cfg is None:
        return None
    return cfg.get("profile", {}).get("profile_id")


__all__ = [
    "load_deploy_config",
    "get_effective_weights",
    "get_arbitrator_mode",
    "get_deploy_policy",
    "get_deploy_agents",
    "get_deploy_profile_id",
]
