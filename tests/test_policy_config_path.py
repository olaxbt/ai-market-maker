from __future__ import annotations

from pathlib import Path


def test_policy_config_path_overrides_defaults(tmp_path: Path, monkeypatch):
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
""".strip(),
        encoding="utf-8",
    )

    from config.fund_policy import load_fund_policy

    p = load_fund_policy(path=cfg)
    assert p.stop_loss_pct == 0.12
    assert p.take_profit_pct == 0.25
    assert p.max_leverage == 3
    assert p.trade_cooldown_bars == 96


def test_load_fund_policy_reads_repo_default():
    """Smoke: repo default policy file must be present and parseable."""
    from config.fund_policy import load_fund_policy

    p = load_fund_policy()
    assert p.max_leverage >= 1.0
