"""Opt-in configuration for leaderboard result submission.

Controls whether and how local agents submit backtest/scan results
to the centralized leaderboard API.

Settings are read from environment vars so they work in Docker, OpenClaw,
and pure local dev without config file changes.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class LeaderboardSubmitConfig:
    """Parsed leaderboard submission opt-in configuration."""

    # Global toggle
    enabled: bool = False

    # Per-type opt-in
    submit_backtests: bool = False
    submit_scans: bool = False

    # Server target
    leaderboard_url: str = ""
    provider: str = ""
    provider_key: str = ""

    # Override for local dev (no remote server)
    local_fallback: bool = True


_ENV_PREFIX = "AIMM_LB_"


def load_leaderboard_submit_config() -> LeaderboardSubmitConfig:
    """Read submission config from env vars.

    Required env:
        AIMM_LB_ENABLED=1           — Enable submission (default: 0)
        AIMM_LB_URL=...             — Leaderboard server URL
        AIMM_LB_PROVIDER=...        — Provider identifier
        AIMM_LB_PROVIDER_KEY=...    — Provider auth key

    Optional env:
        AIMM_LB_SUBMIT_BACKTESTS=0  — Opt-out of backtest submission (default: 1)
        AIMM_LB_SUBMIT_SCANS=0      — Opt-out of scan submission (default: 1)
        AIMM_LB_LOCAL_FALLBACK=1    — Write to local JSONL even without server

    Examples:
        # Minimal local-only (writes to .runs/leadpage/local_scan_results.jsonl)
        AIMM_LB_ENABLED=1

        # Full remote submission
        AIMM_LB_ENABLED=1
        AIMM_LB_URL=https://leaderboard.olaxbt.xyz
        AIMM_LB_PROVIDER=my-agent-v1
        AIMM_LB_PROVIDER_KEY=sk-...

        # Scans only, no backtests
        AIMM_LB_ENABLED=1
        AIMM_LB_URL=https://leaderboard.olaxbt.xyz
        AIMM_LB_SUBMIT_BACKTESTS=0
        AIMM_LB_PROVIDER=my-agent-v2
        AIMM_LB_PROVIDER_KEY=sk-...
    """

    def _env_bool(name: str, default: bool = False) -> bool:
        v = (os.getenv(name) or "").strip().lower()
        if not v:
            return default
        return v in ("1", "true", "yes", "on")

    cfg = LeaderboardSubmitConfig(
        enabled=_env_bool(f"{_ENV_PREFIX}ENABLED"),
        submit_backtests=_env_bool(f"{_ENV_PREFIX}SUBMIT_BACKTESTS", default=True),
        submit_scans=_env_bool(f"{_ENV_PREFIX}SUBMIT_SCANS", default=True),
        leaderboard_url=(os.getenv(f"{_ENV_PREFIX}URL") or "").strip(),
        provider=(os.getenv(f"{_ENV_PREFIX}PROVIDER") or "").strip(),
        provider_key=(os.getenv(f"{_ENV_PREFIX}PROVIDER_KEY") or "").strip(),
        local_fallback=_env_bool(f"{_ENV_PREFIX}LOCAL_FALLBACK", default=True),
    )

    return cfg


def mask_key(key: str) -> str:
    """Return a masked version of the provider key for display."""
    if not key:
        return ""
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]
