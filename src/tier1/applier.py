"""Deterministic Tier-1 Applier: blueprint + HedgeFund state → ExecutionPayload."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from tier1.models import (
    ExecutionPayload,
    ExecutionRoutingPayload,
    MaCrossPayload,
    StopLossPayload,
    StrategyBlueprint,
    TacticalParameters,
    TakeProfitPayload,
    TradeManagementPayload,
    TrailingStopPayload,
)
from tier1.resolvers import eval_operator, resolve_metric
from tier1.validate import log_blueprint_warnings, strict_validate_blueprint_weights

logger = logging.getLogger(__name__)


def load_blueprint_path(path: str | Path) -> StrategyBlueprint:
    raw = Path(path).read_text(encoding="utf-8")
    data = json.loads(raw)
    return StrategyBlueprint.model_validate(data)


def _symbol_for_execution(ticker: str) -> str:
    return str(ticker or "BTC/USDT").replace("/", "").replace("-", "").upper()


def _veto_triggers(
    blueprint: StrategyBlueprint, state: dict[str, Any]
) -> tuple[bool, str | None, bool, bool]:
    """Returns (full_veto, rule_name, block_long, block_short)."""
    block_long = False
    block_short = False
    tactical = blueprint.tactical_parameters
    for rule in tactical.veto_layer_constraints:
        mid = (rule.metric_id or "").strip()
        if not mid:
            continue
        val = resolve_metric(mid, state)
        if not eval_operator(val, rule.operator, rule.threshold, rule.threshold_array):
            continue
        target = (rule.veto_target or "ALL").upper()
        if target == "ALL":
            return True, rule.rule_name, True, True
        if target == "LONG_ONLY":
            block_long = True
        elif target == "SHORT_ONLY":
            block_short = True
        logger.info("Tier-1 partial veto: %s target=%s", rule.rule_name, target)
    return False, None, block_long, block_short


def _alpha_scores(blueprint: StrategyBlueprint, state: dict[str, Any]) -> tuple[int, int]:
    long_s = 0
    short_s = 0
    for fac in blueprint.tactical_parameters.multi_factor_alpha_matrix:
        mid = (fac.metric_id or "").strip()
        if not mid:
            continue
        val = resolve_metric(mid, state)
        if not eval_operator(val, fac.operator, fac.threshold, fac.threshold_array):
            continue
        w = int(fac.weight_pct)
        vd = (fac.vote_direction or "LONG").upper()
        if vd == "LONG":
            long_s += w
        elif vd == "SHORT":
            short_s += w
    return long_s, short_s


def _entry_price(state: dict[str, Any], ticker: str) -> float | None:
    md = state.get("market_data") or {}
    sym = md.get(ticker) if isinstance(md, dict) else None
    if not isinstance(sym, dict):
        return None
    ohlcv = sym.get("ohlcv")
    if not isinstance(ohlcv, list) or not ohlcv:
        return None
    last = ohlcv[-1]
    if isinstance(last, (list, tuple)) and len(last) > 4:
        try:
            return float(last[4])
        except (TypeError, ValueError):
            return None
    return None


def _effective_min_convergence(tactical: TacticalParameters) -> int:
    base = int(tactical.min_convergence_score_required)
    ease = float(tactical.entry_ease_fraction)
    return max(1, int(round(base * (1.0 - ease))))


def _apply_persona_signal_mix(
    long_s: int, short_s: int, blueprint: StrategyBlueprint
) -> tuple[int, int]:
    mix = blueprint.persona_genetics.persona_signal_mix
    if mix is None:
        return long_s, short_s
    ls, ss = long_s, short_s
    if mix.long_bias is not None:
        lb = max(0.0, min(1.0, float(mix.long_bias)))
        ls += int(round((lb - 0.5) * 40))
    style = (
        mix.trend_weight
        + mix.momentum_weight
        - mix.mean_revert_weight
        + 0.25 * mix.volume_weight
        - 0.25 * mix.volatility_weight
    )
    if abs(style) > 1e-6:
        scale = 1.0 + 0.15 * style
        scale = max(0.75, min(1.25, scale))
        ls = int(round(ls * scale))
        ss = int(round(ss * (2.0 - scale)))
    return max(0, ls), max(0, ss)


def _account_notional_hint(state: dict[str, Any]) -> float:
    sm = state.get("shared_memory") or {}
    if not isinstance(sm, dict):
        return 10_000.0
    bt = sm.get("backtest")
    if isinstance(bt, dict):
        try:
            return max(0.0, float(bt.get("cash", 0.0)))
        except (TypeError, ValueError):
            pass
    return 10_000.0


def apply_strategy(
    state: dict[str, Any],
    blueprint: StrategyBlueprint,
    *,
    ticker: str | None = None,
) -> ExecutionPayload:
    """Run Phase 2–4: vetoes, weighted alpha, sizing / TP-SL (simplified where Tier-0 lacks VPVR)."""
    tick = ticker or str(state.get("ticker") or "BTC/USDT")
    sym = _symbol_for_execution(tick)
    log_blueprint_warnings(blueprint)
    strict_validate_blueprint_weights(blueprint)
    meta = {
        "strategy_name": blueprint.strategy_metadata.strategy_name,
        "risk_appetite": blueprint.persona_genetics.risk_appetite,
        "preset": blueprint.strategy_metadata.target_universe,
    }

    full_veto, veto_name, block_long, block_short = _veto_triggers(blueprint, state)
    if full_veto:
        return ExecutionPayload(
            symbol=sym,
            signal="VETO",
            conviction_score=0,
            veto_rule_triggered=veto_name,
            blueprint_meta=meta,
        )

    long_s, short_s = _alpha_scores(blueprint, state)
    long_s, short_s = _apply_persona_signal_mix(long_s, short_s, blueprint)
    min_req = _effective_min_convergence(blueprint.tactical_parameters)
    meta["effective_min_convergence"] = min_req
    permitted = {
        x.upper() for x in (blueprint.persona_genetics.permitted_directions or ["LONG", "SHORT"])
    }

    signal: Any = "HOLD"
    conviction = max(long_s, short_s)

    can_long = "LONG" in permitted and not block_long
    can_short = "SHORT" in permitted and not block_short

    if long_s >= min_req and long_s >= short_s and can_long:
        signal = "EXECUTE_LONG"
        conviction = long_s
    elif short_s >= min_req and short_s > long_s and can_short:
        signal = "EXECUTE_SHORT"
        conviction = short_s
    elif (
        long_s >= min_req and long_s > short_s and not can_long and can_short and short_s >= min_req
    ):
        signal = "EXECUTE_SHORT"
        conviction = short_s
    elif (
        short_s >= min_req and short_s > long_s and not can_short and can_long and long_s >= min_req
    ):
        signal = "EXECUTE_LONG"
        conviction = long_s

    cap = blueprint.capital_directives
    tm = blueprint.trade_management_logic
    sl_crit = tm.stop_loss_criteria
    tp_crit = tm.take_profit_criteria
    entry = _entry_price(state, tick)
    notional_base = _account_notional_hint(state)
    risk_pct = float(cap.max_portfolio_risk_per_trade_pct)
    lev = float(cap.base_leverage_multiplier)
    if cap.max_leverage_multiplier is not None:
        lev = min(lev, float(cap.max_leverage_multiplier))
    position_usdt = max(
        0.0,
        min(notional_base * cap.max_total_position_pct, notional_base * risk_pct * max(1.0, lev)),
    )

    slip_cap = int(cap.execution_routing.max_acceptable_slippage_bps)
    liq_slip = resolve_metric("liq_slippage", state)
    twap = isinstance(liq_slip, int) and slip_cap > 0 and liq_slip > slip_cap + 50

    sl_price = None
    tp_price = None
    adj_log = ""
    if entry is not None and entry > 0 and signal in ("EXECUTE_LONG", "EXECUTE_SHORT"):
        if sl_crit.sl_fixed_pct is not None and sl_crit.sl_fixed_pct > 0:
            pct = float(sl_crit.sl_fixed_pct) / 100.0
            if signal == "EXECUTE_LONG":
                sl_price = entry * (1.0 - pct)
                tp_price = entry + (entry - sl_price) * float(tp_crit.target_rr_ratio)
            else:
                sl_price = entry * (1.0 + pct)
                tp_price = entry - (sl_price - entry) * float(tp_crit.target_rr_ratio)
        else:
            atr_frac = 0.01 * float(sl_crit.sl_atr_multiplier)
            if signal == "EXECUTE_LONG":
                sl_price = entry * (1.0 - atr_frac)
                tp_price = entry + (entry - sl_price) * float(tp_crit.target_rr_ratio)
            else:
                sl_price = entry * (1.0 + atr_frac)
                tp_price = entry - (sl_price - entry) * float(tp_crit.target_rr_ratio)
            adj_log = "synthetic_atr_frac=1pct*multiplier (Tier-0 contract has no atr_pct)"

    return ExecutionPayload(
        symbol=sym,
        signal=signal,
        conviction_score=int(conviction),
        veto_rule_triggered=None,
        execution_routing=ExecutionRoutingPayload(
            order_type="MARKET",
            entry_price=entry,
            position_size_usdt=round(position_usdt, 2),
            leverage=lev,
            twap_required=bool(twap),
        ),
        trade_management=TradeManagementPayload(
            stop_loss=StopLossPayload(price=sl_price, type="STOP_MARKET", adjustment_log=adj_log),
            take_profit=TakeProfitPayload(price=tp_price, type="LIMIT", target_hvn_anchor=False),
            trailing_stop=TrailingStopPayload(
                enabled=tm.trailing_stop.enabled,
                activation_pct=float(tm.trailing_stop.activation_pct),
                instruction=tm.trailing_stop.instruction,
            ),
            ma_cross=MaCrossPayload(
                enabled=tm.ma_cross_periods.enabled,
                fast_period=int(tm.ma_cross_periods.fast_period),
                slow_period=int(tm.ma_cross_periods.slow_period),
            ),
        ),
        blueprint_meta=meta,
    )


__all__ = ["apply_strategy", "load_blueprint_path"]
