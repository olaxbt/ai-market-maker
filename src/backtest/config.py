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

    from backtest.agentic_defaults import (
        DEFAULT_AGENTIC_PROFILE_ID,
        default_agentic_decision_threshold,
        default_agentic_profile_weights,
    )

    result: dict[str, Any] = {
        "arbitrator_mode": ARBITRATOR_AGENT_LLM,
        "profile_weights": default_agentic_profile_weights(),
        "profile_id": DEFAULT_AGENTIC_PROFILE_ID,
        "decision_threshold": default_agentic_decision_threshold(),
        "allows_short": True,
        "use_llm": True,
        "take_profit_pct": 0.0,
        "stop_loss_pct": 0.0,
        "leverage": 2.0,
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
    if use_llm_env in ("0", "false", "no", "off"):
        logger.warning(
            "AI_MARKET_MAKER_USE_LLM=0 is ignored; agentic backtests require LLM (agent_llm)."
        )

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

        dt = deploy_cfg.get("decision_threshold")
        if isinstance(dt, dict) and dt:
            result["decision_threshold"] = dict(dt)

        exec_allows = (deploy_cfg.get("execution") or {}).get("allows_short")
        if exec_allows is not None:
            result["allows_short"] = bool(exec_allows)

        profile_id = (
            deploy_cfg.get("profile", {}).get("profile_id")
            if isinstance(deploy_cfg.get("profile"), dict)
            else None
        )
        if profile_id:
            result["profile_id"] = str(profile_id)

        exec_cfg = deploy_cfg.get("execution") or {}
        tp_raw = exec_cfg.get("take_profit_pct")
        sl_raw = exec_cfg.get("stop_loss_pct")
        lev = exec_cfg.get("leverage") or result["leverage"]
        mhb = exec_cfg.get("max_hold_bars") or result["max_hold_bars"]
        # Deploy config stores TP/SL as fractions (e.g. 0.025 = 2.5%);
        # the engine compares against unrealized P&L in percent (2.5).
        if tp_raw is not None:
            result["take_profit_pct"] = float(tp_raw) * 100.0
        if sl_raw is not None:
            result["stop_loss_pct"] = float(sl_raw) * 100.0
        result["leverage"] = float(lev) if lev else 2.0
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
    if result["arbitrator_mode"] == ARBITRATOR_WEIGHTED_CONVERGENCE:
        logger.warning(
            "weighted_convergence is deprecated for product runs; defaulting to agent_llm."
        )
        result["arbitrator_mode"] = ARBITRATOR_AGENT_LLM
        result["use_llm"] = True

    from backtest.symbol_routing import resolve_agent_led_symbols

    result["agent_led_symbols"] = sorted(
        resolve_agent_led_symbols(deploy_cfg=deploy_cfg if deploy_cfg else None)
    )

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
    mode = str(cfg.get("arbitrator_mode") or ARBITRATOR_AGENT_LLM)
    if mode == ARBITRATOR_WEIGHTED_CONVERGENCE:
        mode = ARBITRATOR_AGENT_LLM
    os.environ["AIMM_ARBITRATOR_MODE"] = mode
    os.environ.pop("AI_MARKET_MAKER_USE_LLM", None)
    os.environ.pop("AIMM_LLM_MODE", None)
    # Enable file-backed agent decision cache (historical bars are deterministic).
    os.environ["MODE"] = "backtest"

    if os.environ.get("AIMM_BACKTEST_VERBOSE_RECEIPTS") is None:
        os.environ["AIMM_BACKTEST_VERBOSE_RECEIPTS"] = "1"

    from backtest.terminal_log import configure_backtest_terminal_logging

    configure_backtest_terminal_logging()

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
