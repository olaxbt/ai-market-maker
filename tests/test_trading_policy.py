"""TradingPolicyManager: ordered exits vs adds and categorization."""

from __future__ import annotations

from dataclasses import replace

from config.fund_policy import load_fund_policy
from trading.policy_manager import (
    DecisionCategory,
    PortfolioDecisionContext,
    TradingPolicyConfig,
    TradingPolicyManager,
)


def _cfg(**kw) -> TradingPolicyConfig:
    # TradingPolicyConfig is an alias of FundPolicy; start from validated defaults and override.
    base = load_fund_policy()
    # Make tests deterministic (avoid env-sensitive defaults like leverage=3, short=false, TP=0.20).
    base = replace(
        base,
        max_leverage=1.0,
        take_profit_pct=0.0,
        allows_short=True,
        rule_sentiment_buy_min=75.0,
        rule_sentiment_sell_below=50.0,
    )
    return replace(base, **kw)


def _ctx(**kw) -> PortfolioDecisionContext:
    base = dict(
        ticker="BTC/USDT",
        current_price=100_000.0,
        target_quantity=0.1,
        current_quantity=0.05,
        entry_avg_price=90_000.0,
        run_mode="backtest",
        intent_action="BUY",
        intent_confidence=0.9,
        sentiment_score=50.0,
        quant_signal="hold",
        arb_signal="hold",
        ema_sma_regime=None,
        external_cash_usd=10_000.0,
    )
    base.update(kw)
    return PortfolioDecisionContext(**base)


def test_take_profit_before_buy_when_under_target():
    """Previously a long + target > qty could skip TP because the buy branch ran first."""
    m = TradingPolicyManager(
        _cfg(
            take_profit_pct=0.08,
            rule_sentiment_buy_min=75.0,
            rule_sentiment_sell_below=42.0,
        )
    )
    # Entry 90k, TP 8% -> 97.2k; price 100k -> should sell
    out = m.decide(_ctx(current_price=100_000.0, target_quantity=0.2))
    assert out["status"] == "proposed"
    assert out["action"] == "sell"
    assert out["reason"]["category"] == DecisionCategory.RISK_TAKE_PROFIT.value


def test_rule_overlay_sell_runs_before_add():
    m = TradingPolicyManager(
        _cfg(
            rule_sentiment_buy_min=75.0,
            rule_sentiment_sell_below=50.0,
        )
    )
    out = m.decide(
        _ctx(
            current_price=95_000.0,
            current_quantity=0.02,
            target_quantity=0.1,
            intent_action="HOLD",
            intent_confidence=0.5,
            quant_signal="sell",
            sentiment_score=30.0,
        )
    )
    assert out["action"] == "sell"
    assert out["reason"]["category"] == DecisionCategory.RULE_OVERLAY_SELL.value


def test_backtest_rule_overlay_buy_neutral_sentiment_with_quant():
    """Sentiment at neutral 50 still allows quant buy when min floor is 50 (inclusive)."""
    m = TradingPolicyManager(_cfg(rule_sentiment_buy_min=50.0, rule_sentiment_sell_below=50.0))
    out = m.decide(
        _ctx(
            current_price=50_000.0,
            current_quantity=0.0,
            entry_avg_price=0.0,
            target_quantity=0.1,
            intent_action="HOLD",
            intent_confidence=0.5,
            sentiment_score=50.0,
            quant_signal="buy",
            arb_signal="hold",
        )
    )
    assert out["status"] == "proposed"
    assert out["action"] == "buy"


def test_backtest_rule_overlay_buy_on_hold_matches_paper():
    """Backtest must not require explicit BUY intent when tape overlay is bullish (symmetry with sells)."""
    m = TradingPolicyManager(
        _cfg(
            rule_sentiment_buy_min=75.0,
            rule_sentiment_sell_below=50.0,
        )
    )
    out = m.decide(
        _ctx(
            current_price=50_000.0,
            current_quantity=0.0,
            entry_avg_price=0.0,
            target_quantity=0.1,
            intent_action="HOLD",
            intent_confidence=0.5,
            sentiment_score=80.0,
            quant_signal="buy",
            arb_signal="hold",
        )
    )
    assert out["status"] == "proposed"
    assert out["action"] == "buy"
    assert out["reason"]["category"] == DecisionCategory.RULE_OVERLAY_BUY.value


def test_backtest_notional_cap_tighter_than_base_cap():
    """Optional USD cap applies per-symbol (alts vs misleading ``*_MAX_ADD_BTC`` units)."""
    m = TradingPolicyManager(
        _cfg(
            order_max_add_btc=0.05,
            order_max_add_notional_usd=2000.0,
            rule_sentiment_buy_min=50.0,
            rule_sentiment_sell_below=50.0,
        )
    )
    out = m.decide(
        _ctx(
            current_price=100_000.0,
            current_quantity=0.0,
            entry_avg_price=0.0,
            target_quantity=1.0,
            intent_action="BUY",
            intent_confidence=0.9,
            quant_signal="hold",
            arb_signal="hold",
        )
    )
    assert out["status"] == "proposed"
    assert out["action"] == "buy"
    assert abs(float(out["quantity"]) - 0.02) < 1e-9


def test_strong_buy_blocks_rule_overlay_sell():
    m = TradingPolicyManager(
        _cfg(
            rule_sentiment_buy_min=75.0,
            rule_sentiment_sell_below=50.0,
        )
    )
    out = m.decide(
        _ctx(
            current_price=95_000.0,
            current_quantity=0.02,
            target_quantity=0.1,
            intent_action="BUY",
            intent_confidence=0.8,
            quant_signal="sell",
            sentiment_score=30.0,
        )
    )
    assert out["action"] == "buy"
