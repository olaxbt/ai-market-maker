"""Central trading policy: categorizes decisions and applies a single ordered rule stack.

Order of evaluation (fixes a common bug where a long target size blocked exits):

1. **Risk bind** — stop-loss / take-profit vs average entry (not vs trailing bar low).
2. **Discretionary exit** — SELL intent or (backtest-only) rule-based bearish overlay.
3. **Add / open** — BUY when under target; **intent BUY** or the same **sentiment/quant/arb overlay** as paper/live (backtest is not intent-only on the buy side).

Policy **numbers** come from :func:`config.fund_policy.load_fund_policy`; this module encodes **semantics** only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from config.fund_policy import FundPolicy, load_fund_policy
from config.run_mode import is_backtest_run

# Backward-compatible names (tests, re-exports).
TradingPolicyConfig = FundPolicy
load_trading_policy_from_env = load_fund_policy


@dataclass(frozen=True)
class PortfolioDecisionContext:
    ticker: str
    current_price: float
    target_quantity: float
    current_quantity: float
    entry_avg_price: float
    run_mode: str
    intent_action: str
    intent_confidence: float
    sentiment_score: float
    quant_signal: str
    arb_signal: str
    #: Optional regime label from TA adapter (e.g. ema/sma up/down).
    ema_sma_regime: str | None
    external_cash_usd: float | None


class DecisionCategory(str, Enum):
    HOLD = "hold"
    RISK_STOP_LOSS = "risk_stop_loss"
    RISK_TAKE_PROFIT = "risk_take_profit"
    INTENT_SELL = "intent_sell"
    RULE_OVERLAY_SELL = "rule_overlay_sell"
    INTENT_BUY = "intent_buy"
    RULE_OVERLAY_BUY = "rule_overlay_buy"


class TradingPolicyManager:
    def __init__(self, config: FundPolicy | None = None):
        self.config = config or load_fund_policy()

    def decide(self, ctx: PortfolioDecisionContext) -> dict[str, Any]:
        cfg = self.config
        backtest = is_backtest_run(ctx.run_mode)
        action = str(ctx.intent_action or "HOLD").upper()
        conf_f = (
            float(ctx.intent_confidence) if isinstance(ctx.intent_confidence, (int, float)) else 0.0
        )
        min_c = cfg.min_confidence_directional
        is_intent_driven = action in ("BUY", "SELL") and conf_f >= min_c

        current_price = float(ctx.current_price)
        current_quantity = float(ctx.current_quantity)
        entry_px = float(ctx.entry_avg_price)
        target_quantity = float(ctx.target_quantity)

        quant_s = _norm_signal(ctx.quant_signal)
        arb_s = _norm_signal(ctx.arb_signal)
        regime = str(ctx.ema_sma_regime or "").strip().lower()

        stop_pct = cfg.stop_loss_pct
        tp_pct = cfg.take_profit_pct

        forced_cat: DecisionCategory | None = None
        if current_quantity > 1e-12 and entry_px > 1e-12:
            if stop_pct > 0 and current_price <= entry_px * (1.0 - stop_pct):
                forced_cat = DecisionCategory.RISK_STOP_LOSS
            elif tp_pct > 0 and current_price >= entry_px * (1.0 + tp_pct):
                forced_cat = DecisionCategory.RISK_TAKE_PROFIT

        if forced_cat is not None:
            return {
                "status": "proposed",
                "action": "sell",
                "quantity": current_quantity,
                "reason": {
                    "category": forced_cat.value,
                    "entry_avg_price": entry_px,
                    "current_price": current_price,
                    "stop_loss_pct": stop_pct,
                    "take_profit_pct": tp_pct,
                },
            }

        strong_buy = action == "BUY" and conf_f >= min_c
        intent_sell = action == "SELL" and conf_f >= min_c and (is_intent_driven or backtest)

        allow_rule_overlay = backtest
        rule_sell = False
        if allow_rule_overlay and current_quantity > 1e-12 and not strong_buy:
            rule_sell = arb_s == "sell" or (
                quant_s == "sell" and float(ctx.sentiment_score) < cfg.rule_sentiment_sell_below
            )

        if current_quantity > 1e-12 and (intent_sell or rule_sell):
            # Bull participation: when regime is up, don't churn out of longs on discretionary signals.
            # Risk binds (stop/take) are handled above and still fire.
            if backtest and regime == "up":
                return {
                    "status": "skipped",
                    "message": "Bull regime: hold winners (skip discretionary sell)",
                }
            cat = (
                DecisionCategory.INTENT_SELL if intent_sell else DecisionCategory.RULE_OVERLAY_SELL
            )
            return {
                "status": "proposed",
                "action": "sell",
                "quantity": current_quantity,
                "reason": {
                    "category": cat.value,
                    "intent_action": action,
                    "confidence": conf_f,
                    "sentiment_score": ctx.sentiment_score,
                    "quant_signal": quant_s,
                    "arb_signal": arb_s,
                    "target_quantity": target_quantity,
                    "current_quantity": current_quantity,
                },
            }

        trade_result: dict[str, Any] = {"status": "skipped", "message": "No trade signal"}

        # Risk-off cap: in down regime, reduce exposure towards a capped target even without explicit SELL intent.
        if backtest and regime == "down" and target_quantity > 1e-12 and current_quantity > 1e-12:
            cap_f = max(0.0, min(1.0, float(cfg.bear_max_target_fraction)))
            cap_q = cap_f * target_quantity
            if current_quantity > cap_q + 1e-12:
                return {
                    "status": "proposed",
                    "action": "sell",
                    "quantity": current_quantity - cap_q,
                    "reason": {
                        "category": "bear_max_exposure",
                        "ema_sma_regime": regime,
                        "bear_max_target_fraction": cap_f,
                        "target_quantity": target_quantity,
                        "current_quantity": current_quantity,
                    },
                }

        # Bull participation: when regime is up, enforce holding a minimum fraction of target.
        if backtest and regime == "up" and target_quantity > 1e-12:
            floor = max(0.0, min(1.0, float(cfg.bull_min_target_fraction)))
            min_q = floor * target_quantity
            if current_quantity + 1e-12 < min_q:
                quantity_to_buy = min_q - current_quantity
                if ctx.external_cash_usd is not None and current_price > 0:
                    cash_f = float(ctx.external_cash_usd)
                    quantity_to_buy = min(quantity_to_buy, cash_f / current_price)
                    eq = cash_f + current_quantity * current_price
                    max_notional = max(0.0, eq * cfg.max_leverage)
                    headroom_usd = max(0.0, max_notional - current_quantity * current_price)
                    quantity_to_buy = min(quantity_to_buy, headroom_usd / current_price)
                if quantity_to_buy > 1e-12:
                    return {
                        "status": "proposed",
                        "action": "buy",
                        "quantity": quantity_to_buy,
                        "reason": {
                            "category": "bull_min_exposure",
                            "ema_sma_regime": regime,
                            "bull_min_target_fraction": floor,
                            "target_quantity": target_quantity,
                            "current_quantity": current_quantity,
                        },
                    }

        if target_quantity > current_quantity:
            if is_intent_driven:
                buy_signal = action == "BUY"
            else:
                # Same tape-reading overlay as paper/live: backtest used to require explicit BUY
                # intent only, which starved entries whenever the thesis was HOLD/neutral.
                if action in ("BUY", "SELL"):
                    buy_signal = action == "BUY" and conf_f >= min_c
                else:
                    buy_signal = (
                        float(ctx.sentiment_score) >= cfg.rule_sentiment_buy_min
                        and quant_s == "buy"
                    ) or (arb_s == "buy")
                    if backtest and regime == "up":
                        # Bull regime: allow opening/adding even when thesis is HOLD.
                        buy_signal = True
                    elif backtest and regime == "down":
                        # Risk-off regime: don't open new longs on weak/no signals.
                        buy_signal = False

            if buy_signal:
                quantity_to_buy = target_quantity - current_quantity
                src = "intent" if is_intent_driven else "rule_overlay"
                if backtest:
                    add_cap = float(cfg.order_max_add_btc)
                    if cfg.order_max_add_notional_usd is not None and current_price > 0:
                        add_cap = min(
                            add_cap, float(cfg.order_max_add_notional_usd) / current_price
                        )
                    quantity_to_buy = min(quantity_to_buy, add_cap)
                    if ctx.external_cash_usd is not None and current_price > 0:
                        cash_f = float(ctx.external_cash_usd)
                        quantity_to_buy = min(quantity_to_buy, cash_f / current_price)
                        eq = cash_f + current_quantity * current_price
                        max_notional = max(0.0, eq * cfg.max_leverage)
                        headroom_usd = max(0.0, max_notional - current_quantity * current_price)
                        cap_lev = headroom_usd / current_price
                        quantity_to_buy = min(quantity_to_buy, cap_lev)

                cat = (
                    DecisionCategory.INTENT_BUY
                    if is_intent_driven
                    else DecisionCategory.RULE_OVERLAY_BUY
                )
                trade_result = {
                    "status": "proposed",
                    "action": "buy",
                    "quantity": quantity_to_buy,
                    "reason": {
                        "category": cat.value,
                        "source": src,
                        "sentiment_score": ctx.sentiment_score,
                        "quant_signal": quant_s,
                        "arb_signal": arb_s,
                        "target_quantity": target_quantity,
                        "current_quantity": current_quantity,
                        "confidence": conf_f,
                    },
                }

        return trade_result


def _norm_signal(s: Any) -> str:
    return str(s or "hold").strip().lower()
