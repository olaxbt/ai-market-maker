"""Deterministic execution intent from thesis (``proposed_signal``).

Tier-2 synthesis (``signal_arbitrator`` / LLM) and Tier-1 applier both emit
``stance`` + ``confidence`` on ``proposed_signal.params``. This module is the
single adapter to discrete ``BUY`` / ``SELL`` / ``HOLD`` for portfolio sizing —
no duplicate graph node, no second policy engine.
"""

from __future__ import annotations

from typing import Any, Mapping

from config.fund_policy import load_fund_policy
from config.run_mode import RunMode

# Default gate for tests / docs (live value is :attr:`FundPolicy.min_confidence_directional`).
# Keep this aligned with FundPolicy defaults to avoid surprising test behavior.
MIN_CONFIDENCE_DIRECTIONAL = 0.45

META_SOURCE = "execution_intent_v1"


def derive_trade_intent(
    state: Mapping[str, Any],
    proposed_signal: Mapping[str, Any],
) -> dict[str, Any]:
    """Map thesis (stance + confidence) → portfolio-facing intent contract."""
    ticker = str(state.get("ticker") or "BTC/USDT")
    run_mode = str(state.get("run_mode") or "paper").lower()
    sm = state.get("shared_memory") or {}
    bt = sm.get("backtest") if isinstance(sm, dict) and isinstance(sm.get("backtest"), dict) else {}
    cash = float(bt.get("cash", 0.0)) if run_mode == RunMode.BACKTEST.value else None
    qty = float(bt.get("qty", 0.0)) if run_mode == RunMode.BACKTEST.value else None

    md = state.get("market_data") or {}
    price = None
    try:
        price = float(((md.get(ticker) or {}).get("ohlcv") or [])[-1][4])
    except Exception:
        price = None

    params = proposed_signal.get("params") if isinstance(proposed_signal, dict) else None
    params = params if isinstance(params, dict) else {}
    stance = params.get("stance")
    confidence = params.get("confidence")
    reasons = params.get("reasons")

    stance_s = str(stance or "neutral").lower()
    conf_f = float(confidence) if isinstance(confidence, (int, float)) else 0.5
    if stance_s not in ("bullish", "bearish", "neutral"):
        stance_s = "neutral"
    if not isinstance(reasons, list):
        reasons = []
    reasons_out = [str(r) for r in reasons]

    fp = load_fund_policy()
    min_c = fp.min_confidence_directional
    action = "HOLD"
    if stance_s == "bullish" and conf_f >= min_c:
        action = "BUY"
    elif stance_s == "bearish" and conf_f >= min_c:
        action = "SELL"
        if not fp.allows_short and run_mode == RunMode.BACKTEST.value:
            pos_dict = bt.get("positions")
            if isinstance(pos_dict, dict):
                total_base = sum(float(v) for v in pos_dict.values() if isinstance(v, (int, float)))
                if total_base <= 1e-12:
                    action = "HOLD"
                    reasons_out.insert(
                        0,
                        "execution_intent: bearish→HOLD (AIMM_ALLOW_SHORT=0, flat multi-asset backtest book)",
                    )
            elif qty is not None and float(qty) <= 1e-12:
                action = "HOLD"
                reasons_out.insert(
                    0,
                    "execution_intent: bearish→HOLD (AIMM_ALLOW_SHORT=0, flat backtest book)",
                )

    max_notional_usd = None
    if run_mode == RunMode.BACKTEST.value and cash is not None:
        # Align with :class:`config.fund_policy.FundPolicy` (not a separate 10% rule).
        max_notional_usd = (
            max(0.0, float(cash)) * fp.intent_notional_fraction * float(fp.max_leverage)
        )

    return {
        "ticker": ticker,
        "action": action,
        "confidence": round(max(0.0, min(0.95, conf_f)), 2),
        "reasons": reasons_out[:12],
        "constraints": {
            "max_notional_usd": max_notional_usd,
            "requires_price": True,
        },
        "context": {
            "run_mode": run_mode,
            "cash_usd": cash,
            "qty_base": qty,
            "price": price,
        },
        "meta": {
            "source": META_SOURCE,
            "derived_from": "proposed_signal.params.stance",
            "min_confidence_directional": min_c,
        },
    }


__all__ = ["MIN_CONFIDENCE_DIRECTIONAL", "META_SOURCE", "derive_trade_intent"]
