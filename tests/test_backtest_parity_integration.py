"""Integration tests for deploy → backtest config parity."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from backtest.config import resolve_backtest_config, set_env_from_config

DEPLOY_AGENT_LLM = {
    "effective_weights": {"agent_a": 0.3, "agent_b": 0.2},
    "execution": {
        "arbitrator_mode": "agent_llm",
        "take_profit_pct": 5.0,
        "stop_loss_pct": 5.0,
        "leverage": 5.0,
        "max_hold_bars": 48,
    },
    "profile": {"profile_id": "prod-v2"},
    "agents": {"agent_a": {}, "agent_b": {}},
}

DEPLOY_WEIGHTED = {
    "effective_weights": {"trend": 0.5, "momentum": 0.5},
    "execution": {
        "arbitrator_mode": "weighted_convergence",
        "take_profit_pct": 3.0,
        "stop_loss_pct": 3.0,
        "leverage": 3.0,
    },
    "profile": {"profile_id": "quant-v1"},
    "agents": {},
}


class TestConfigParity:
    def test_agent_llm_mode_no_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            dp = Path(tmp) / "deploy.active.json"
            dp.write_text(json.dumps(DEPLOY_AGENT_LLM), encoding="utf-8")
            cfg = resolve_backtest_config(deploy_path=str(dp))

            assert cfg["arbitrator_mode"] == "agent_llm"
            assert cfg["use_llm"] is True
            assert cfg["deploy_loaded"] is True
            assert cfg["profile_id"] == "prod-v2"
            assert cfg["profile_weights"] == {"agent_a": 0.3, "agent_b": 0.2}
            assert cfg["take_profit_pct"] == 5.0
            assert cfg["stop_loss_pct"] == 5.0
            assert cfg["max_hold_bars"] == 48

    def test_weighted_mode_no_llm_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            dp = Path(tmp) / "deploy.active.json"
            dp.write_text(json.dumps(DEPLOY_WEIGHTED), encoding="utf-8")
            cfg = resolve_backtest_config(deploy_path=str(dp))

            assert cfg["arbitrator_mode"] == "weighted_convergence"
            assert cfg["use_llm"] is False
            assert cfg["take_profit_pct"] == 3.0
            assert cfg["leverage"] == 3.0

    def test_cli_mode_overrides_deploy(self):
        with tempfile.TemporaryDirectory() as tmp:
            dp = Path(tmp) / "deploy.active.json"
            dp.write_text(json.dumps(DEPLOY_WEIGHTED), encoding="utf-8")
            cfg = resolve_backtest_config(
                deploy_path=str(dp),
                cli_arbitrator_mode="agent_llm",
            )
            assert cfg["arbitrator_mode"] == "agent_llm"
            assert cfg["use_llm"] is True

    def test_set_env_agent_llm(self):
        cfg = resolve_backtest_config(cli_arbitrator_mode="agent_llm")
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_ARBITRATOR_MODE") == "agent_llm"

    def test_set_env_weighted(self):
        cfg = resolve_backtest_config(cli_arbitrator_mode="weighted_convergence")
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_ARBITRATOR_MODE") is None
        assert os.environ.get("AI_MARKET_MAKER_USE_LLM") == "0"


class TestDefaultDeployPath:
    def test_picks_up_default_deploy_file(self):
        orig_cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            deploy_dir = Path(tmp) / "config"
            deploy_dir.mkdir(exist_ok=True)
            dp = deploy_dir / "deploy.active.json"
            dp.write_text(json.dumps(DEPLOY_AGENT_LLM), encoding="utf-8")

            cfg = resolve_backtest_config()
            assert cfg["deploy_loaded"] is True
            assert cfg["arbitrator_mode"] == "agent_llm"
        os.chdir(orig_cwd)

    def test_no_deploy_file_fallback(self):
        if "AIMM_DEPLOY_CONFIG_PATH" in os.environ:
            del os.environ["AIMM_DEPLOY_CONFIG_PATH"]

        cfg = resolve_backtest_config()
        assert cfg["deploy_loaded"] is False
        assert cfg["arbitrator_mode"] == "weighted_convergence"
        assert cfg["use_llm"] is False


class TestEnvParity:
    def test_env_ai_market_maker_use_llm(self):
        cfg = resolve_backtest_config(env={"AI_MARKET_MAKER_USE_LLM": "1"})
        assert cfg["arbitrator_mode"] == "agent_llm"
        assert cfg["use_llm"] is True

    def test_env_deploy_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            dp = Path(tmp) / "my_deploy.json"
            dp.write_text(json.dumps(DEPLOY_AGENT_LLM), encoding="utf-8")
            cfg = resolve_backtest_config(
                deploy_path=str(dp),
                env={"AIMM_DEPLOY_CONFIG_PATH": str(dp)},
            )
            assert cfg["deploy_loaded"] is True

    def teardown_method(self):
        os.environ.pop("AIMM_ARBITRATOR_MODE", None)
        os.environ.pop("AI_MARKET_MAKER_USE_LLM", None)
        os.environ.pop("AIMM_DEPLOY_CONFIG_PATH", None)
