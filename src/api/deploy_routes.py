"""Deploy-config endpoint — full configuration validation and deployment.

Accepts an end-to-end trading configuration payload from the Config UI,
validates the schema, writes to disk, and makes the config available for
the next run cycle.

This is the bridge between the web UI config wizard and the backend runtime.
Without this endpoint, users cannot deploy anything.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

router = APIRouter(tags=["deploy"])


# ── Constants ────────────────────────────────────────────────────────────

_DEFAULT_DEPLOY_PATH = "config/deploy.active.json"
_AGENT_WEIGHTS_DEFAULT: dict[str, float] = {
    "1.1": 0.05,  # monetary_sentinel
    "1.2": 0.05,  # news_narrative_miner
    "2.1": 0.25,  # pattern_recognition_bot
    "2.2": 0.10,  # statistical_alpha_engine
    "2.3": 0.30,  # technical_ta_engine
    "3.1": 0.05,  # retail_hype_tracker
    "3.2": 0.05,  # pro_bias_analyst
    "4.1": 0.05,  # whale_behavior_analyst
    "4.2": 0.15,  # liquidity_order_flow
}

_AGENT_LABELS: dict[str, str] = {
    "1.1": "Monetary Sentinel",
    "1.2": "News & Narrative Miner",
    "2.1": "Pattern Recognition Bot",
    "2.2": "Statistical Alpha Engine",
    "2.3": "Technical TA Engine",
    "3.1": "Retail Hype Tracker",
    "3.2": "Pro Bias Analyst",
    "4.1": "Whale Behavior Analyst",
    "4.2": "Liquidity & Order Flow",
}

_GRAPH_EDGES_DEFAULT: list[dict[str, str]] = [
    {"from": "policy_orchestrator", "to": "market_scan"},
    {"from": "market_scan", "to": "tier0"},
    {"from": "tier0", "to": "desk_risk"},
    {"from": "desk_risk", "to": "desk_debate"},
    {"from": "desk_debate", "to": "weighted_arbitrator"},
    {"from": "weighted_arbitrator", "to": "execution_intent"},
    {"from": "execution_intent", "to": "portfolio_proposal"},
    {"from": "portfolio_proposal", "to": "risk_guard"},
    {"from": "risk_guard", "to": "portfolio_execute"},
]


# ── Pydantic Models ──────────────────────────────────────────────────────


class AgentNodeConfig(BaseModel):
    """Per-agent node configuration with v4.1 LLM enhancements."""

    id: str
    enabled: bool = True
    llm_enabled: bool = False
    persona_path: str | None = None
    temperature: float = 0.0
    weight_override: float | None = None
    label: str | None = None


class PolicyConfig(BaseModel):
    """Config UI policy knobs (subset deployed to disk)."""

    portfolio_budget_usd: float = 10000
    stop_loss_pct: float = 0.025
    take_profit_pct: float = 0.06
    max_leverage: float = 2.0
    min_confidence_directional: float = 0.26
    allows_short: bool = True
    trade_cooldown_bars: int = 10
    bull_exposure_floor: float = 0.65
    bear_exposure_cap: float = 0.35
    risk_max_drawdown_stop: float | None = 0.12
    risk_kill_switch_cooldown_bars: int = 120

    @field_validator("max_leverage")
    @classmethod
    def leverage_range(cls, v: float) -> float:
        return max(1.0, min(100.0, v))

    @field_validator("stop_loss_pct", "take_profit_pct", "risk_max_drawdown_stop")
    @classmethod
    def clamp_pct(cls, v: float | None) -> float | None:
        if v is None:
            return None
        return max(0.0, min(0.95, v))


class ExecConfig(BaseModel):
    """Execution / run-time settings."""

    arbitrator_mode: str = Field(
        default="weighted_convergence",
        description="weighted_convergence | agent_llm",
    )
    desk_debate_enabled: bool = False
    nexus_api_key: str | None = None
    default_ticker: str = "BTC/USDT"
    universe_symbols: list[str] = Field(
        default_factory=lambda: [
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "AIO/USDT",
            "BNB/USDT",
            "XRP/USDT",
            "ADA/USDT",
        ],
    )


class ProfileWeights(BaseModel):
    """Profile-based weight overrides (from Profile Agent or manual)."""

    profile_id: str | None = None
    deltas: dict[str, str] = Field(default_factory=dict)
    narrative: str | None = None


class DeployConfigRequest(BaseModel):
    """Full end-to-end configuration payload from the Config UI."""

    name: str = Field(default="default", max_length=120)
    description: str = Field(default="", max_length=500)

    # Core settings
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    execution: ExecConfig = Field(default_factory=ExecConfig)

    # Agent topology
    agents: list[AgentNodeConfig] = Field(default_factory=list)
    edges: list[dict[str, str]] | None = None

    # Profile overrides
    profile: ProfileWeights = Field(default_factory=ProfileWeights)


class DeployConfigResponse(BaseModel):
    ok: bool
    path: str
    config_id: str
    timestamp: str
    validation: dict[str, Any]
    preview: dict[str, Any] | None = None


# ── Helpers ──────────────────────────────────────────────────────────────


def _deploy_path() -> Path:
    override = (os.getenv("AIMM_DEPLOY_CONFIG_PATH") or "").strip()
    return Path(override) if override else Path(_DEFAULT_DEPLOY_PATH)


def _resolve_effective_weights(
    agents: list[AgentNodeConfig],
    profile: ProfileWeights,
) -> dict[str, float]:
    """Build effective weight map: defaults + per-agent overrides + profile deltas."""
    weights = dict(_AGENT_WEIGHTS_DEFAULT)

    # Per-agent weight overrides
    for agent in agents:
        aid = agent.id
        if agent.weight_override is not None:
            weights[aid] = agent.weight_override

    # Profile deltas (string format: "+0.05" or "-0.03")
    for aid, delta_str in profile.deltas.items():
        try:
            delta = float(delta_str.replace("+", ""))
            if delta_str.startswith("+"):
                weights[aid] = weights.get(aid, 0.05) + delta
            elif delta_str.startswith("-"):
                weights[aid] = weights.get(aid, 0.05) - delta
            else:
                weights[aid] = delta  # absolute
            weights[aid] = max(0.0, min(1.0, weights[aid]))
        except (ValueError, TypeError):
            pass

    return weights


def _validate_config(req: DeployConfigRequest) -> dict[str, Any]:
    """Validate the config and return structured warnings/errors."""
    issues: list[str] = []
    warnings: list[str] = []

    # Validate agent IDs
    valid_ids = set(_AGENT_LABELS.keys())
    known_ids = {a.id for a in req.agents}
    unknown = known_ids - valid_ids
    if unknown:
        warnings.append(f"Unknown agent ids: {', '.join(sorted(unknown))}")

    # Check mandatory agents
    mandatory = {"2.1", "2.3"}  # core TA agents
    missing_mandatory = mandatory - known_ids
    if missing_mandatory:
        warnings.append(
            f"Missing core agents (will add defaults): {', '.join(sorted(missing_mandatory))}"
        )

    # Validate arbitrator_mode
    if req.execution.arbitrator_mode not in ("weighted_convergence", "agent_llm"):
        issues.append(
            f"Invalid arbitrator_mode: {req.execution.arbitrator_mode}. "
            f"Use 'weighted_convergence' or 'agent_llm'."
        )

    # Validate leverage
    if req.policy.max_leverage > 10:
        warnings.append(f"High leverage: {req.policy.max_leverage}x")

    return {"valid": len(issues) == 0, "issues": issues, "warnings": warnings}


# ── Routes ───────────────────────────────────────────────────────────────


@router.post("/deploy-config", response_model=DeployConfigResponse)
async def deploy_config(req: DeployConfigRequest) -> dict[str, Any]:
    """Validate and deploy a full end-to-end configuration.

    Accepts the complete config from the UI wizard, runs validation,
    writes the active config to disk, and returns the result.
    """
    config_id = f"cfg_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}"
    timestamp = datetime.now(timezone.utc).isoformat()

    # Validate
    validation = _validate_config(req)

    # Compute effective weights
    effective_weights = _resolve_effective_weights(req.agents, req.profile)

    # Build agent map
    agent_map: dict[str, dict[str, Any]] = {}
    for agent in req.agents:
        aid = agent.id
        agent_map[aid] = {
            "id": aid,
            "label": agent.label or _AGENT_LABELS.get(aid, aid),
            "enabled": agent.enabled,
            "llm_enabled": agent.llm_enabled,
            "persona_path": agent.persona_path or f"operator/{aid}/persona.md",
            "temperature": agent.temperature,
            "weight": effective_weights.get(aid, 0.05),
        }

    # Build edges
    edges = req.edges or _GRAPH_EDGES_DEFAULT

    # Preview for the UI
    preview = {
        "agent_count": len(agent_map),
        "arbitrator_mode": req.execution.arbitrator_mode,
        "effective_weights": {aid: round(w, 4) for aid, w in sorted(effective_weights.items())},
        "profile_id": req.profile.profile_id,
    }

    # Build the full deployment payload
    deploy_payload: dict[str, Any] = {
        "config_id": config_id,
        "deployed_at": timestamp,
        "name": req.name,
        "description": req.description,
        "policy": req.policy.model_dump(),
        "execution": req.execution.model_dump(),
        "agents": agent_map,
        "edges": edges,
        "profile": req.profile.model_dump(),
        "effective_weights": effective_weights,
        "validation": validation,
    }

    # Write to disk
    try:
        path = _deploy_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(deploy_payload, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to write deploy config: {e}",
        ) from e

    return DeployConfigResponse(
        ok=True,
        path=str(path),
        config_id=config_id,
        timestamp=timestamp,
        validation=validation,
        preview=preview,
    ).model_dump()


@router.get("/deploy-config")
async def get_active_deploy_config() -> dict[str, Any]:
    """Return the currently active deployed configuration."""
    path = _deploy_path()
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="No active deploy config. POST to /deploy-config first.",
        )
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj
    except (json.JSONDecodeError, OSError) as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read deploy config: {e}",
        ) from e


@router.post("/deploy-config/apply", response_model=DeployConfigResponse)
async def apply_deploy_config(req: DeployConfigRequest) -> dict[str, Any]:
    """Validate, deploy, and apply config changes to the running system.

    Same as POST /deploy-config, but also writes the execution settings
    into runtime_settings.json so the running system picks them up
    without restart.
    """
    # First deploy
    result = await deploy_config(req)

    # If successful, also write runtime settings
    if result.get("ok"):
        try:
            exec_settings = req.execution.model_dump()
            policy_settings = req.policy.model_dump()

            import os as _os
            from pathlib import Path as _Path

            rt_path_env = (_os.getenv("AIMM_RUNTIME_SETTINGS_PATH") or "").strip()
            rt_path = _Path(rt_path_env) if rt_path_env else _Path("config/runtime_settings.json")

            existing = {}
            if rt_path.is_file():
                existing = json.loads(rt_path.read_text(encoding="utf-8"))

            existing["policy"] = {**existing.get("policy", {}), **policy_settings}
            existing["execution"] = {**existing.get("execution", {}), **exec_settings}
            existing["deploy_ref"] = result.get("config_id", "")

            rt_path.parent.mkdir(parents=True, exist_ok=True)
            rt_path.write_text(
                json.dumps(existing, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
        except OSError as e:
            result["warning"] = f"Deploy written, but runtime apply failed: {e}"

    return result


@router.get("/deploy-config/schema")
async def deploy_config_schema() -> dict[str, Any]:
    """Return the expected schema for the deploy-config endpoint.

    Useful for the Config UI to generate the form dynamically.
    """
    return {
        "agent_ids": list(_AGENT_LABELS.keys()),
        "agent_labels": _AGENT_LABELS,
        "default_weights": _AGENT_WEIGHTS_DEFAULT,
        "default_edges": _GRAPH_EDGES_DEFAULT,
        "arbitrator_modes": ["weighted_convergence", "agent_llm"],
        "valid_modes": ["weighted_convergence", "agent_llm"],
    }


__all__ = ["router"]
