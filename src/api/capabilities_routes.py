"""Capabilities endpoint.

This makes the UI truthful: it can discover what the backend can do in the
current deployment (hosted leaderboard vs full local runner).
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter

from config.app_settings import load_app_settings
from config.env_parse import env_bool

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def get_capabilities() -> dict[str, Any]:
    # Keep this minimal and stable; prefer reflecting "can I do X" over listing config.
    require_keys = env_bool(os.environ, "LEADPAGE_REQUIRE_KEYS", default=False)
    require_signed = env_bool(os.environ, "LEADPAGE_REQUIRE_SIGNED", default=False)
    has_provider_keys = bool((os.getenv("LEADPAGE_PROVIDER_KEYS") or "").strip())

    settings = load_app_settings()
    hosted = env_bool(
        os.environ, "AIMM_HOSTED_STUDIO", default=settings.control_plane.hosted_studio
    )
    ops_enabled = bool(settings.control_plane.ops_enabled)

    return {
        "mode_hint": "hosted" if hosted else "local",
        "leaderboard": {
            "external_submit_requires_key": require_keys,
            "external_submit_requires_signature": require_signed,
            "provider_keys_configured": has_provider_keys,
        },
        "ops": {
            "can_run_backtests": ops_enabled,
            "can_publish_backtest_via_ops": ops_enabled,
            "runtime_settings_supported": True,
        },
    }
