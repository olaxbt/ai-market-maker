"""Tests for backtest config resolver."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from backtest.config import (
    ARBITRATOR_AGENT_LLM,
    resolve_backtest_config,
    resolve_tp_sl_pct,
    set_env_from_config,
)


def _sample_deploy_config(
    *,
    mode: str = "agent_llm",
    tp: float = 0.05,
    sl: float = 0.05,
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
        cfg = resolve_backtest_config(deploy_path="/nonexistent/aimm-deploy-missing.json")
        assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM
        assert cfg["use_llm"] is True
        assert cfg["deploy_loaded"] is False
        assert cfg["profile_weights"] == {"2.3": 0.55, "2.1": 0.15, "1.1": 0.25}
        assert cfg["profile_id"] == "macro_tilt"
        assert cfg["allows_short"] is True
        assert cfg["decision_threshold"]["ta_led"]["enabled"] is True

    def test_shipped_deploy_active_json(self):
        root = Path(__file__).resolve().parents[1]
        deploy = root / "config" / "deploy.active.json"
        if not deploy.is_file():
            return
        cfg = resolve_backtest_config(deploy_path=str(deploy))
        assert cfg["deploy_loaded"] is True
        assert cfg["profile_id"] == "macro_tilt"
        assert cfg["profile_weights"] == {"2.3": 0.55, "2.1": 0.15, "1.1": 0.25}
        assert cfg["leverage"] == 2.0

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
            assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM
            assert cfg["use_llm"] is True
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
        assert cfg["arbitrator_mode"] == ARBITRATOR_AGENT_LLM

    def test_cli_leverage(self):
        cfg = resolve_backtest_config(
            deploy_path="/nonexistent/aimm-deploy-missing.json",
            cli_leverage=10.0,
        )
        assert cfg["leverage"] == 10.0

        cfg2 = resolve_backtest_config(
            deploy_path="/nonexistent/aimm-deploy-missing.json",
            cli_leverage=0.0,
        )
        assert cfg2["leverage"] == 2.0

    def test_policy_tp_sl_when_deploy_omits(self):
        """Deploy without TP/SL falls back to fund policy."""
        with tempfile.TemporaryDirectory() as tmp:
            deploy_path = Path(tmp) / "deploy.active.json"
            deploy_path.write_text(
                json.dumps(
                    {
                        "effective_weights": {"2.3": 1.0},
                        "execution": {"arbitrator_mode": "agent_llm", "leverage": 2.0},
                        "profile": {"profile_id": "no-tp-sl"},
                    }
                ),
                encoding="utf-8",
            )
            cfg = resolve_backtest_config(deploy_path=str(deploy_path))
            assert cfg["deploy_loaded"] is True
            assert cfg["take_profit_pct"] == pytest.approx(6.0)
            assert cfg["stop_loss_pct"] == pytest.approx(2.5)

    def test_no_deploy_falls_back_to_policy_tp_sl(self):
        cfg = resolve_backtest_config(deploy_path="/nonexistent/aimm-deploy-missing.json")
        assert cfg["deploy_loaded"] is False
        assert cfg["take_profit_pct"] == pytest.approx(6.0)
        assert cfg["stop_loss_pct"] == pytest.approx(2.5)


class TestResolveTpSlPct:
    def test_cli_wins(self):
        tp, sl = resolve_tp_sl_pct(
            cli_tp_sl_pct=4.0,
            deploy_execution={"take_profit_pct": 0.05, "stop_loss_pct": 0.03},
        )
        assert tp == 4.0
        assert sl == 4.0

    def test_deploy_fractions(self):
        tp, sl = resolve_tp_sl_pct(
            deploy_execution={"take_profit_pct": 0.05, "stop_loss_pct": 0.03},
        )
        assert tp == pytest.approx(5.0)
        assert sl == pytest.approx(3.0)

    def test_policy_fallback_injectable(self):
        from types import SimpleNamespace

        tp, sl = resolve_tp_sl_pct(
            fund_policy=SimpleNamespace(take_profit_pct=0.06, stop_loss_pct=0.025),
        )
        assert tp == pytest.approx(6.0)
        assert sl == pytest.approx(2.5)

    def test_policy_mirrors_tp_when_sl_zero(self):
        from types import SimpleNamespace

        tp, sl = resolve_tp_sl_pct(
            fund_policy=SimpleNamespace(take_profit_pct=0.08, stop_loss_pct=0.0),
        )
        assert tp == pytest.approx(8.0)
        assert sl == pytest.approx(8.0)


class TestSetEnvFromConfig:
    def test_sets_agent_llm_env(self):
        cfg = resolve_backtest_config(cli_arbitrator_mode="agent_llm")
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_ARBITRATOR_MODE") == "agent_llm"
        assert os.environ.get("AI_MARKET_MAKER_USE_LLM") is None
        assert os.environ.get("AIMM_LLM_MODE") is None

    def test_weighted_convergence_upgrades_to_agent_llm(self):
        cfg = resolve_backtest_config(cli_arbitrator_mode="weighted_convergence")
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_ARBITRATOR_MODE") == "agent_llm"

    def test_deploy_active_signal(self):
        cfg = resolve_backtest_config(deploy_path="/nonexistent")
        cfg["deploy_loaded"] = True
        set_env_from_config(cfg)
        assert os.environ.get("AIMM_DEPLOY_ACTIVE") == "1"

    def teardown_method(self):
        os.environ.pop("AIMM_ARBITRATOR_MODE", None)
        os.environ.pop("AIMM_DEPLOY_ACTIVE", None)
        os.environ.pop("AI_MARKET_MAKER_USE_LLM", None)
        os.environ.pop("AIMM_LLM_MODE", None)


class TestLoopResolvedConfigStamp:
    def test_stamps_engine_tp_sl_over_deploy_zeros(self, tmp_path, monkeypatch):
        """Stamp engine TP/SL into summary resolved_config."""
        summary_path = tmp_path / "summary.json"
        summary_path.write_text(
            json.dumps({"leverage": 3.0, "steps": 1, "eval_bars": 1}),
            encoding="utf-8",
        )
        (tmp_path / "trades.jsonl").write_text("", encoding="utf-8")

        class _FakeEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **_kwargs):
                return {
                    "run_id": "bt_tp_sl_stamp",
                    "steps": 1,
                    "interval_sec": 300,
                    "trade_count": 0,
                    "metrics": {},
                    "final_equity": 10_000.0,
                    "paths": {
                        "summary": str(summary_path),
                        "trades": str(tmp_path / "trades.jsonl"),
                        "equity": str(tmp_path / "equity.csv"),
                        "events": str(tmp_path / "events.jsonl"),
                    },
                }

        monkeypatch.setattr("backtest.loop.BacktestEngine", _FakeEngine)

        from backtest.loop import run_multi_step_backtest

        bars = [[1_700_000_000_000, 1.0, 2.0, 0.5, 100.0, 10.0]]
        res = run_multi_step_backtest(
            ticker="BTC/USDT",
            bars=bars,
            take_profit_pct=6.0,
            stop_loss_pct=2.5,
            deploy_config={
                "take_profit_pct": 0.0,
                "stop_loss_pct": 0.0,
                "leverage": 2.0,
            },
            runs_dir=tmp_path,
            export_bundle=False,
            ta_warmup_bars=0,
        )
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        rc = summary["resolved_config"]
        assert rc["take_profit_pct"] == 6.0
        assert rc["stop_loss_pct"] == 2.5
        assert rc["leverage"] == 3.0
        assert res.resolved_config is not None
        assert res.resolved_config["take_profit_pct"] == 6.0
        assert res.resolved_config["stop_loss_pct"] == 2.5
