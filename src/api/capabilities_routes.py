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
        # Explicit contract for console surfaces — what feeds Research / Portfolio / Live.
        "dashboard_sources": {
            "research": [
                {
                    "label": "OHLCV candles",
                    "api": "GET /backtests/{id}/bars",
                    "source": "Exchange / Yahoo / Futu → .runs/backtests/<id>/bars.json",
                },
                {
                    "label": "Strategy equity",
                    "api": "GET /backtests/{id}/equity",
                    "source": "Simulated book MTM → equity.jsonl",
                },
                {
                    "label": "Fills",
                    "api": "GET /backtests/{id}/trades",
                    "source": "Fill model (signal on completed bar → next open)",
                },
                {
                    "label": "KPIs + benchmark",
                    "api": "GET /backtests/{id}/summary",
                    "source": "Engine metrics + buy&hold vs primary symbol",
                },
                {
                    "label": "Agent timeline",
                    "api": "GET /runs/{id}/payload",
                    "source": "Per-bar node events / thoughts",
                },
            ],
            "portfolio": [
                {
                    "label": "Book equity",
                    "api": "GET /pm/portfolio-health",
                    "source": "Live account free cash + margin locked",
                },
                {
                    "label": "Positions",
                    "api": "GET /pm/portfolio-health",
                    "source": ".runs/paper/<account>.account.json (or live adapter)",
                },
            ],
            "live": [
                {
                    "label": "Agent thoughts",
                    "api": "WS /ws/runs/{id}",
                    "source": "Live iteration or followed backtest run",
                },
                {
                    "label": "Session controls",
                    "api": "POST /engine/paper/start|stop",
                    "source": "Live loop interval + ticker",
                },
            ],
        },
    }
