"""Backtest config: merge deploy JSON, env vars, and CLI overrides."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_DEPLOY_PATH = "config/deploy.active.json"

ARBITRATOR_AGENT_LLM = "agent_llm"
ARBITRATOR_WEIGHTED_CONVERGENCE = "weighted_convergence"

VALID_ARBITRATOR_MODES = (ARBITRATOR_AGENT_LLM, ARBITRATOR_WEIGHTED_CONVERGENCE)


def resolve_backtest_config(
    *,
    deploy_path: str | None = None,
    cli_arbitrator_mode: str | None = None,
    cli_tp_sl_pct: float | None = None,
    cli_leverage: float | None = None,
    cli_max_hold_bars: int | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Merge deploy config, environment, and CLI overrides."""
    if env is None:
        env = dict(os.environ)

    result: dict[str, Any] = {
        "arbitrator_mode": ARBITRATOR_WEIGHTED_CONVERGENCE,
        "profile_weights": {},
        "profile_id": "",
        "use_llm": False,
        "take_profit_pct": 0.0,
        "stop_loss_pct": 0.0,
        "leverage": 3.0,
        "max_hold_bars": 0,
        "deploy_path": "",
        "deploy_loaded": False,
        "source_description": "defaults",
    }

    env_arb_mode = (env.get("AIMM_ARBITRATOR_MODE") or "").strip().lower()
    if env_arb_mode in VALID_ARBITRATOR_MODES:
        result["arbitrator_mode"] = env_arb_mode

    env_deploy_path = (env.get("AIMM_DEPLOY_CONFIG_PATH") or "").strip()
    if env_deploy_path:
        deploy_path = env_deploy_path

    use_llm_env = (env.get("AI_MARKET_MAKER_USE_LLM") or "").strip()
    if use_llm_env in ("1", "true", "yes"):
        if result["arbitrator_mode"] == ARBITRATOR_WEIGHTED_CONVERGENCE:
            result["arbitrator_mode"] = ARBITRATOR_AGENT_LLM

    deploy_cfg: dict[str, Any] | None = None
    effective_deploy_path = deploy_path or DEFAULT_DEPLOY_PATH
    deploy_file = Path(effective_deploy_path)
    if deploy_file.is_file():
        try:
            deploy_cfg = json.loads(deploy_file.read_text(encoding="utf-8"))
            if not isinstance(deploy_cfg, dict):
                deploy_cfg = None
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("failed to read deploy config at %s: %s", effective_deploy_path, e)
            deploy_cfg = None

    if deploy_cfg is not None:
        result["deploy_path"] = str(deploy_file.resolve())
        result["deploy_loaded"] = True

        deploy_arb_mode = (deploy_cfg.get("execution") or {}).get("arbitrator_mode")
        if deploy_arb_mode in VALID_ARBITRATOR_MODES:
            result["arbitrator_mode"] = deploy_arb_mode

        ew = deploy_cfg.get("effective_weights")
        if isinstance(ew, dict):
            result["profile_weights"] = dict(ew)

        profile_id = (
            deploy_cfg.get("profile", {}).get("profile_id")
            if isinstance(deploy_cfg.get("profile"), dict)
            else None
        )
        if profile_id:
            result["profile_id"] = str(profile_id)

        exec_cfg = deploy_cfg.get("execution") or {}
        tp = exec_cfg.get("take_profit_pct") or result["take_profit_pct"]
        sl = exec_cfg.get("stop_loss_pct") or result["stop_loss_pct"]
        lev = exec_cfg.get("leverage") or result["leverage"]
        mhb = exec_cfg.get("max_hold_bars") or result["max_hold_bars"]
        result["take_profit_pct"] = float(tp) if tp else 0.0
        result["stop_loss_pct"] = float(sl) if sl else 0.0
        result["leverage"] = float(lev) if lev else 3.0
        result["max_hold_bars"] = int(mhb) if mhb else 0

    if cli_arbitrator_mode is not None and cli_arbitrator_mode.strip():
        mode = cli_arbitrator_mode.strip().lower()
        if mode in VALID_ARBITRATOR_MODES:
            result["arbitrator_mode"] = mode
        else:
            logger.warning("unknown arbitrator mode %r, ignoring", mode)

    if cli_tp_sl_pct is not None and cli_tp_sl_pct > 0:
        result["take_profit_pct"] = float(cli_tp_sl_pct)
        result["stop_loss_pct"] = float(cli_tp_sl_pct)

    if cli_leverage is not None and cli_leverage >= 1.0:
        result["leverage"] = float(cli_leverage)

    if cli_max_hold_bars is not None and cli_max_hold_bars > 0:
        result["max_hold_bars"] = int(cli_max_hold_bars)

    result["use_llm"] = result["arbitrator_mode"] == ARBITRATOR_AGENT_LLM

    parts = []
    if result["deploy_loaded"]:
        parts.append(f"deploy:{result['deploy_path']}")
    parts.append(f"mode:{result['arbitrator_mode']}")
    parts.append(f"tp:{result['take_profit_pct']}")
    parts.append(f"lev:{result['leverage']}")
    if cli_arbitrator_mode is not None:
        parts.append("cli-override")
    result["source_description"] = "|".join(parts)

    return result


def set_env_from_config(cfg: dict[str, Any]) -> None:
    """Apply resolved config to process environment."""
    if cfg.get("arbitrator_mode") == ARBITRATOR_AGENT_LLM:
        os.environ["AI_MARKET_MAKER_USE_LLM"] = "1"
        os.environ["AIMM_ARBITRATOR_MODE"] = "agent_llm"
    else:
        os.environ["AI_MARKET_MAKER_USE_LLM"] = "0"
        os.environ.pop("AIMM_ARBITRATOR_MODE", None)

    if cfg.get("deploy_loaded"):
        os.environ["AIMM_DEPLOY_ACTIVE"] = "1"


def available_arbitrator_modes() -> list[str]:
    return list(VALID_ARBITRATOR_MODES)


__all__ = [
    "ARBITRATOR_AGENT_LLM",
    "ARBITRATOR_WEIGHTED_CONVERGENCE",
    "VALID_ARBITRATOR_MODES",
    "available_arbitrator_modes",
    "resolve_backtest_config",
    "set_env_from_config",
]
