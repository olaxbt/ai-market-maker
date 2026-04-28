from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from storage.leadpage_db import database_url as _db_url
from storage.leadpage_db import feed_signals as _db_feed_signals
from storage.leadpage_db import leaderboard_rows as _db_leaderboard_rows
from storage.leadpage_db import provider_rows as _db_provider_rows

router = APIRouter(tags=["public"])


@router.get("/public/providers/{provider}/profile")
def get_provider_profile(provider: str) -> dict[str, Any]:
    """Public provider profile payload for shareable pages."""
    if not _db_url():
        return {"provider": provider, "enabled": False}
    signals = _db_feed_signals(limit=20, provider=provider)
    leaderboard = _db_leaderboard_rows(limit=30, provider=provider, sort_by="return")
    results = _db_provider_rows(provider, limit=30)
    return {
        "enabled": True,
        "provider": provider,
        "signals_preview": signals,
        "leaderboard_preview": leaderboard,
        "results_preview": results,
    }
