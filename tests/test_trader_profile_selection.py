from __future__ import annotations

from pathlib import Path


def test_agent_prompts_profile_selects_preset_when_present(monkeypatch) -> None:
    from config import agent_prompts

    monkeypatch.delenv("AIMM_AGENT_PROMPTS_PATH", raising=False)
    monkeypatch.delenv("AIMM_TRADING_STYLE", raising=False)
    monkeypatch.setenv("AIMM_TRADER_PROFILE", "buffett")

    p = agent_prompts._default_prompts_path()
    assert str(p).endswith("config/agent_prompts.buffett.json")
    assert p.is_file()


def test_agent_prompts_explicit_path_wins(monkeypatch, tmp_path: Path) -> None:
    from config import agent_prompts

    f = tmp_path / "agent_prompts.json"
    f.write_text("[]\n", encoding="utf-8")
    monkeypatch.setenv("AIMM_AGENT_PROMPTS_PATH", str(f))
    monkeypatch.setenv("AIMM_TRADER_PROFILE", "buffett")
    monkeypatch.setenv("AIMM_TRADING_STYLE", "active")

    p = agent_prompts._default_prompts_path()
    assert p == f


def test_load_fund_policy_uses_env_config_path(monkeypatch, tmp_path: Path) -> None:
    cfg = tmp_path / "policy.json"
    cfg.write_text(
        """
{
  "policy": {
    "stop_loss_pct": 0.12,
    "take_profit_pct": 0.25,
    "max_leverage": 3,
    "min_confidence_directional": 0.55,
    "trade_cooldown_bars": 96,
    "allows_short": true,
    "order_max_add_btc": 0.02,
    "order_max_add_notional_usd": null,
    "intent_notional_fraction": 0.1,
    "rule_sentiment_buy_min": 55,
    "rule_sentiment_sell_below": 40,
    "bull_exposure_floor": 0.5,
    "bear_exposure_cap": 0.2,
    "risk_max_drawdown_stop": 0.25,
    "risk_kill_switch_cooldown_bars": 120,
    "portfolio_budget_usd": 6000,
    "risk_position_cap_usd": 1500
  }
}
""".strip()
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("AIMM_CONFIG_PATH", str(cfg))
    from config.fund_policy import load_fund_policy

    p = load_fund_policy()
    assert p.stop_loss_pct == 0.12
    assert p.max_leverage == 3
