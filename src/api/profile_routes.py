"""Profile Agent API routes — personalised weight generation."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/profile-agent", tags=["profile"])


class ProfileQuestionnaire(BaseModel):
    """User-facing 5-question trading-style assessment."""

    risk_tolerance: str = Field(..., description="conservative | moderate | aggressive")
    time_horizon: str = Field(..., description="scalping | intraday | swing | position")
    preferred_signals: str = Field(
        ..., description="technical | onchain | news | sentiment | mixed"
    )
    leverage_comfort: str = Field(..., description="1x | 1-3x | 3-5x | 5x+")
    assets: str = Field(..., description="majors_only | majors_alts | full_universe")


@router.post("/generate")
async def generate_profile(q: ProfileQuestionnaire) -> dict[str, Any]:
    """Generate a personalised agent-weight profile from user questionnaire.

    Uses the ProfileAgent (rule-based by default, LLM-enhanced when
    AIMM_LLM_PROFILE=1).

    Returns: profile_id, deltas, effective_weights, narrative.
    """
    try:
        from agents.profile_agent import ProfileAgent

        agent = ProfileAgent()
        result = agent.process(
            {
                "risk_tolerance": q.risk_tolerance,
                "time_horizon": q.time_horizon,
                "preferred_signals": q.preferred_signals,
                "leverage_comfort": q.leverage_comfort,
                "assets": q.assets,
            }
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/labels")
async def agent_labels() -> dict[str, str]:
    """Return the agent ID -> label mapping for UI."""
    from agents.profile_agent import AGENT_LABELS

    return dict(AGENT_LABELS)


@router.get("/default-weights")
async def default_weights() -> dict[str, float]:
    """Return the default AGENT_WEIGHTS_DEFAULT."""
    from agents.profile_agent import AGENT_WEIGHTS_DEFAULT

    return dict(AGENT_WEIGHTS_DEFAULT)


@router.get("/list")
async def list_profiles() -> list[dict]:
    """List all stored profiles (profile_id + narrative + created_at)."""
    from agents.profile_registry import list_profiles as _list_profiles

    return _list_profiles()


@router.post("/save")
async def save_profile(profile: dict) -> dict:
    """Save a profile JSON to persistent storage.

    The profile must contain a ``profile_id`` key.
    """
    from agents.profile_registry import save_profile as _save_profile

    ok = _save_profile(profile)
    return {"saved": ok, "profile_id": profile.get("profile_id", "")}


@router.get("/load/{profile_id}")
async def load_profile(profile_id: str) -> dict:
    """Load a profile by profile_id.

    Returns 404 if not found.
    """
    from agents.profile_registry import load_profile as _load_profile

    profile = _load_profile(profile_id)
    if profile is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"Profile {profile_id} not found")
    return profile
