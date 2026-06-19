"""Tests for backtest config resolver."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from backtest.config import (
    ARBITRATOR_AGENT_LLM,
    ARBITRATOR_WEIGHTED_CONVERGENCE,
    resolve_backtest_config,
    set_env_from_config,
)


def _sample_deploy_config(
    *,
    mode: str = "agent_llm",
    tp: float = 5.0,
    sl: float = 5.0,
    lev: float = 5.0,
) -> dict:
    return {
        "effective_weights": {"agent_1": 0.15, "agent_2": 0.2},
        "execution": {
            "arbitrator_mode": mode,
            "take_profit_pct": tp,
            "stop_loss_pct": sl,
            "leverage": lev,
        },
        "profile": {"profile_id": "test-profile-v1"},
        "agents": {},
    }


class TestResolveBacktestConfig:
    def test_defaults(self):
        cfg = resolve_backtest_config()
        assert cfg["arbitrator_mode"] == ARBITRATOR_WEIGHTED_CONVERGENCE
        assert cfg["use_llm"] is False
        assert cfg["deploy_loaded"] is False
        assert cfg["profile_weights"] == {}

    def test_deploy_config_loaded(self):
        with tempfile.TemporaryDirectory() as tmp:
            deploy_path = Path(tmp) / "deploy.active.json"
            deploy_path.write_text(json.dumps(_sample_deploy_config()), encoding="utf-8")
            cfg = resolve_backtest_config(deploy_path=str(deploy_path))
            assert cfg["deploy_loaded"] is True
            assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM
            assert cfg["use_llm"] is True
            assert cfg["take_profit_pct"] == 5.0
            assert cfg["stop_loss_pct"] == 5.0
            assert cfg["leverage"] == 5.0
            assert cfg["profile_id"] == "test-profile-v1"
            assert cfg["profile_weights"] == {"agent_1": 0.15, "agent_2": 0.2}

    def test_cli_override_wins_over_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            deploy_path = Path(tmp) / "deploy.active.json"
            deploy_path.write_text(json.dumps(_sample_deploy_config()), encoding="utf-8")
            cfg = resolve_backtest_config(
                deploy_path=str(deploy_path),
                cli_arbitrator_mode="weighted_convergence",
                cli_tp_sl_pct=3.0,
            )
            assert cfg["arbitrator_mode"] == ARBITRATOR_WEIGHTED_CONVERGENCE
            assert cfg["use_llm"] is False
            assert cfg["take_profit_pct"] == 3.0
            assert cfg["stop_loss_pct"] == 3.0
            assert cfg["deploy_loaded"] is True

    def test_env_arbitrator_mode(self):
        cfg = resolve_backtest_config(env={"AIMM_ARBITRATOR_MODE": "agent_llm"})
        assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM
        assert cfg["use_llm"] is True

    def test_env_use_llm(self):
        cfg = resolve_backtest_config(env={"AI_MARKET_MAKER_USE_LLM": "1"})
        assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM
        assert cfg["use_llm"] is True

    def test_deploy_no_file_fallback(self):
        cfg = resolve_backtest_config(deploy_path="/nonexistent/deploy.json")
        assert cfg["deploy_loaded"] is False
        assert cfg["arbitrator_mode"] == ARBITRATOR_WEIGHTED_CONVERGENCE

    def test_cli_leverage(self):
        cfg = resolve_backtest_config(cli_leverage=10.0)
        assert cfg["leverage"] == 10.0

        cfg2 = resolve_backtest_config(cli_leverage=0.0)
        assert cfg2["leverage"] == 3.0


class TestSetEnvFromConfig:
    def test_sets_llm_env(self):
        cfg = resolve_backtest_config(cli_arbitrator_mode="agent_llm")
        set_env_from_config(cfg)
        assert os.environ.get("AI_MARKET_MAKER_USE_LLM") == "1"
        assert os.environ.get("AIMM_ARBITRATOR_MODE") == "agent_llm"

    def test_clears_llm_env_on_weighted(self):
        os.environ["AI_MARKET_MAKER_USE_LLM"] = "1"
        cfg = resolve_backtest_config(cli_arbitrator_mode="weighted_convergence")
        set_env_from_config(cfg)
        assert os.environ.get("AI_MARKET_MAKER_USE_LLM") == "0"

    def test_deploy_active_signal(self):
        cfg = resolve_backtest_config(deploy_path="/nonexistent")
        cfg["deploy_loaded"] = True
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_DEPLOY_ACTIVE") == "1"

    def teardown_method(self):
        os.environ.pop("AI_MARKET_MAKER_USE_LLM", None)
        os.environ.pop("AIMM_ARBITRATOR_MODE", None)
        os.environ.pop("AIMM_DEPLOY_ACTIVE", None)
