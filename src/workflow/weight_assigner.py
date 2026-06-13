"""Factor-weighted Tier-0 signal engine for weighted convergence arbitration."""

from __future__ import annotations

from typing import Any

from schemas.arbitration import (
    AGENT_FACTOR_MAP,
    AGENT_LABEL_MAP,
    AGENT_TYPE_MAP,
    AGENT_WEIGHTS_DEFAULT,
    AgentWeightedSignal,
    ArbitrationResult,
    FactorSignal,
)
from schemas.tier0_contract import tier0_contracts_by_agent


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError, OverflowError):
        return default


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _invert(v: float) -> float:
    """Invert a 0–1 scale so high raw → bullish low / bearish."""
    return 1.0 - v


def _normalize_linear(val: float, raw_max: float, raw_min: float = 0.0) -> float:
    """Map [raw_min, raw_max] → [0, 1], clamp at bounds."""
    span = raw_max - raw_min
    if span <= 0:
        return 0.5
    return _clamp((val - raw_min) / span)


def _agent_1_1_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Monetary Sentinel — macro regime + liquidity score."""
    mrs = _f(contract.get("macro_regime_state"), 1.0)
    ls = _f(contract.get("Liquidity_Score"), 50.0)
    regime_bull = _normalize_linear(mrs, 2.0, 0.0)
    score_bull = _normalize_linear(ls, 100.0, 0.0)
    return {"macro_bias": (regime_bull * 0.6 + score_bull * 0.4)}


def _agent_1_2_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """News & Narrative Miner."""
    ni = _f(contract.get("News_Impact_Score"), 50.0)
    et = str(contract.get("Event_Type") or "Routine")
    # High impact = bearish (uncertainty shock); low impact = neutral/bullish
    sentiment_bull = _invert(_normalize_linear(ni, 100.0, 0.0))
    # Event type mapping: Black Swan→bearish, Routine→bullish
    event_map = {"Routine": 0.55, "Elevated": 0.45, "Major Catalyst": 0.35, "Black Swan": 0.15}
    event_bull = event_map.get(et, 0.50)
    # narrative_freshness — not in contract fields, default neutral
    return {
        "sentiment_score": sentiment_bull,
        "impact_score": sentiment_bull,  # reuse inverted impact
        "event_type": event_bull,
        "narrative_freshness": 0.50,
    }


def _agent_2_1_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Pattern Recognition Bot."""
    ss = _f(contract.get("Setup_Score"), 50.0)
    # pattern_quality — derive from pattern field
    pat = str(contract.get("pattern") or "unknown").lower()
    pat_map = {
        "accumulation": 0.70,
        "vcp": 0.75,
        "cup_handle": 0.65,
        "ascending": 0.60,
        "bull_flag": 0.65,
        "distribution": 0.30,
        "descending": 0.35,
        "bear_flag": 0.35,
        "unknown": 0.50,
    }
    pat_quality = pat_map.get(pat, 0.50)
    # timeframe_align — from kalman_support presence as proxy
    ks = contract.get("kalman_support")
    tfa = 0.55 if ks is not None and _f(ks) > 0 else 0.50
    # volume_conf — simplified from setup score
    vc = _normalize_linear(ss, 100.0, 0.0)
    return {
        "setup_score": _normalize_linear(ss, 100.0, 0.0),
        "pattern_quality": pat_quality,
        "timeframe_align": tfa,
        "volume_conf": vc,
    }


def _agent_2_2_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Statistical Alpha Engine."""
    sig = str(contract.get("alpha_signal") or "Hold")
    sig_map = {"Strong Buy": 0.85, "Buy": 0.65, "Hold": 0.50, "Sell": 0.35, "Strong Sell": 0.15}
    alpha_bull = sig_map.get(sig, 0.50)
    z = _f(contract.get("cross_sectional_z_score"), 0.0)
    # z-score: positive = bullish, negative = bearish, clamp at ±3
    z_bull = _clamp(0.5 + (z / 6.0))  # z=-3→0.0, z=0→0.5, z=+3→1.0
    # regime_fit — not in contract, default neutral
    return {
        "alpha_signal": alpha_bull,
        "z_score": z_bull,
        "regime_fit": 0.50,
    }


def _agent_2_3_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Technical TA Engine."""
    ti = contract.get("ta_indicators") if isinstance(contract.get("ta_indicators"), dict) else {}
    rsi = _f(ti.get("rsi"), 50.0)
    # RSI: oversold < 30 → bullish, overbought > 70 → bearish
    rsi_bull = _invert(_normalize_linear(rsi, 100.0, 0.0))

    macd_hist = _f(ti.get("macd_hist") or ti.get("macd", 0.0), 0.0)
    macd_bull = _clamp(0.5 + macd_hist / (abs(macd_hist) + 1.0) * 0.4)

    obv = _f(ti.get("obv", 0.0), 0.0)
    obv_bull = _clamp(0.5 + obv / (abs(obv) + 1.0) * 0.3)

    atr_pct = _f(ti.get("atr", 0.0), 0.0)
    # Low ATR → stable (neutral bullish), high ATR → volatile (bearish)
    atr_bull = _invert(_clamp(atr_pct / 10.0)) if atr_pct > 0 else 0.50

    adx = _f(ti.get("adx", 0.0), 25.0)
    # ADX > 25 → trending; below → ranging
    adx_bull = _clamp(adx / 50.0)  # 0→0, 25→0.5, 50→1.0

    ema_fast = _f(
        ti.get("ema", {}).get("fast")
        if isinstance(ti.get("ema"), dict)
        else ti.get("ema_fast", 0.0),
        0.0,
    )
    ema_slow = _f(
        ti.get("ema", {}).get("slow")
        if isinstance(ti.get("ema"), dict)
        else ti.get("ema_slow", 0.0),
        0.0,
    )
    if ema_slow > 0:
        ema_bull = _clamp(0.5 + ((ema_fast / ema_slow - 1.0) * 5.0))
    else:
        ema_bull = 0.50

    vol = _f(ti.get("volume", 0.0), 0.0)
    vol_bull = _normalize_linear(vol, 1000000.0)  # rough scaling

    # pattern_rec — from contract pattern field or default
    pat_rec = ti.get("pattern_rec")
    pr_bull = _f(pat_rec, 0.5) if pat_rec is not None else 0.50

    return {
        "rsi": rsi_bull,
        "macd": macd_bull,
        "obv": obv_bull,
        "atr": atr_bull,
        "adx": adx_bull,
        "ema_cross": ema_bull,
        "volume": vol_bull,
        "pattern_rec": pr_bull,
    }


def _agent_3_1_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Retail Hype Tracker."""
    fomo = _f(contract.get("FOMO_Level"), 50.0)
    # High FOMO → bearish (retail euphoria), low FOMO → bullish (fear/despair)
    fomo_bull = _invert(_normalize_linear(fomo, 100.0, 0.0))
    div = contract.get("Divergence_Warning", False)
    # Divergence warning present → bearish
    div_bull = 0.20 if div else 0.55
    # social_volume — not available in contract, derive from FOMO
    social_bull = fomo_bull * 0.5  # inverse proxy
    return {
        "fomo_level": fomo_bull,
        "social_volume": social_bull,
        "divergence_warning": div_bull,
    }


def _agent_3_2_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Pro Bias / Smart Money Tracker."""
    pb = _f(contract.get("Pro_Bias"), 50.0)
    etf_raw = str(contract.get("ETF_Trend") or "Neutral")
    etf_map = {"Accumulation": 0.70, "Neutral": 0.50, "Distribution": 0.30}
    etf_bull = etf_map.get(etf_raw, 0.50)
    # funding_rate / oi_delta — not in current contract, use Pro_Bias as proxy
    fr_bull = _normalize_linear(pb, 100.0, 0.0)
    oi_bull = _normalize_linear(pb, 100.0, 0.0) * 0.5 + 0.25
    return {
        "etf_trend": etf_bull,
        "funding_rate": fr_bull,
        "oi_delta": oi_bull,
    }


def _agent_4_1_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Whale Behavior."""
    dp = _f(contract.get("Dump_Probability"), 0.0)
    # Higher dump probability → bearish
    dp_bull = _invert(_clamp(dp))
    spg = _f(contract.get("Sell_Pressure_Gauge"), 50.0)
    conc_bull = _invert(_normalize_linear(spg, 100.0, 0.0))
    # wallet_flow — not in contract
    return {
        "dump_probability": dp_bull,
        "concentration_pct": conc_bull,
        "wallet_flow": 0.50,
    }


def _agent_4_2_factors(contract: dict[str, Any], state: dict[str, Any]) -> dict[str, float]:
    """Liquidity & Order Flow."""
    slip = _f(contract.get("Slippage_Risk_Score"), 50.0)
    # Higher slippage risk → bearish
    slip_bull = _invert(_normalize_linear(slip, 100.0, 0.0))
    oi = contract.get("Order_Imbalance")
    oi_bull = 0.55 if oi is not None and _f(oi) < 0 else 0.45 if oi is not None else 0.50
    # depth_skew — not in contract
    return {
        "slippage_risk": slip_bull,
        "order_imbalance": oi_bull,
        "depth_skew": 0.50,
    }


# Registry: agent_id → extractor function
_AGENT_EXTRACTORS: dict[str, Any] = {
    "1.1": _agent_1_1_factors,
    "1.2": _agent_1_2_factors,
    "2.1": _agent_2_1_factors,
    "2.2": _agent_2_2_factors,
    "2.3": _agent_2_3_factors,
    "3.1": _agent_3_1_factors,
    "3.2": _agent_3_2_factors,
    "4.1": _agent_4_1_factors,
    "4.2": _agent_4_2_factors,
}


def compute_agent_weighted_signals(
    state: dict[str, Any],
    *,
    agent_weights: dict[str, float] | None = None,
    disabled_agents: set[str] | None = None,
) -> list[AgentWeightedSignal]:
    """Compute per-agent weighted signals from Tier-0 contracts."""
    idx = tier0_contracts_by_agent(state)
    weights = dict(AGENT_WEIGHTS_DEFAULT)
    if agent_weights:
        weights.update(agent_weights)
    disabled = set(disabled_agents or set())

    signals: list[AgentWeightedSignal] = []

    for aid in sorted(AGENT_FACTOR_MAP.keys()):
        contract = idx.get(aid, {})
        extractor = _AGENT_EXTRACTORS.get(aid)
        if extractor is None:
            continue

        raw_factors = extractor(contract, state)
        factor_map = AGENT_FACTOR_MAP.get(aid, {})

        agent_w = weights.get(aid, 0.0)
        enabled = aid not in disabled and bool(contract.get("status") != "error")

        factor_signals: list[FactorSignal] = []
        composite = 0.0
        total_factor_weight = 0.0

        for fid, fw in sorted(factor_map.items(), key=lambda x: x[0]):
            raw_val = raw_factors.get(fid, 0.5)
            norm_val = _clamp(raw_val)
            composite += fw * norm_val
            total_factor_weight += fw

            factor_signals.append(
                FactorSignal(
                    factor_id=fid,
                    agent_id=aid,
                    raw_value=raw_val,
                    normalized=norm_val,
                    weight=fw,
                    enabled=enabled,
                    source_field="",
                )
            )

        # If agent has no defined factors (e.g. 1.1), use raw_factors directly
        if total_factor_weight <= 0 and raw_factors:
            for fid, raw_val in raw_factors.items():
                norm_val = _clamp(raw_val)
                fw = 0.5  # equal weight fallback
                composite += fw * norm_val
                total_factor_weight += fw
                factor_signals.append(
                    FactorSignal(
                        factor_id=fid,
                        agent_id=aid,
                        raw_value=raw_val,
                        normalized=norm_val,
                        weight=fw,
                        enabled=enabled,
                        source_field="",
                    )
                )

        # Normalize composite to [0, 1]
        if total_factor_weight > 0:
            raw_composite = composite / total_factor_weight
        else:
            raw_composite = 0.5
        raw_composite = _clamp(raw_composite)
        weighted = agent_w * raw_composite

        # Map composite to stance
        if raw_composite >= 0.55:
            stance = "bullish"
        elif raw_composite <= 0.45:
            stance = "bearish"
        else:
            stance = "neutral"

        # Confidence from distance to neutral
        conf = _clamp(0.5 + abs(raw_composite - 0.5) * 2.0)

        signals.append(
            AgentWeightedSignal(
                agent_id=aid,
                agent_type=AGENT_TYPE_MAP.get(aid, ""),
                label=AGENT_LABEL_MAP.get(aid, ""),
                composite=raw_composite,
                raw_composite=raw_composite,
                agent_weight=agent_w if enabled else 0.0,
                weighted_composite=weighted if enabled else 0.0,
                factor_signals=factor_signals,
                enabled=enabled,
                confidence=conf,
                stance=stance,
            )
        )

    return signals


def compute_global_weighted_score(
    signals: list[AgentWeightedSignal],
) -> dict[str, Any]:
    """Compute global weighted composite score and confidence."""
    total_weight = sum(s.agent_weight for s in signals if s.enabled)
    if total_weight <= 0:
        return {
            "composite": 0.5,
            "confidence": 0.0,
            "consensus_ratio": 0.0,
            "stance": "neutral",
            "conviction": "none",
        }

    weighted_sum = sum(s.weighted_composite for s in signals if s.enabled)
    composite = _clamp(weighted_sum / total_weight) if total_weight > 0 else 0.5

    enabled_sigs = [s for s in signals if s.enabled]
    total_enabled = max(1, len(enabled_sigs))
    bullish_count = sum(1 for s in enabled_sigs if s.composite >= 0.55)
    bearish_count = sum(1 for s in enabled_sigs if s.composite <= 0.45)
    max_side = max(bullish_count, bearish_count)
    consensus_ratio = max_side / total_enabled

    magnitude = abs(composite - 0.5) * 2.0

    confidence = magnitude * min(1.0, 0.5 + consensus_ratio * 0.5)
    confidence = _clamp(confidence)

    if composite >= 0.55:
        stance = "bullish"
    elif composite <= 0.45:
        stance = "bearish"
    else:
        stance = "neutral"

    # Conviction level
    if confidence >= 0.75:
        conviction = "high"
    elif confidence >= 0.55:
        conviction = "medium"
    elif confidence > 0.0:
        conviction = "low"
    else:
        conviction = "none"

    return {
        "composite": round(composite, 4),
        "confidence": round(confidence, 4),
        "consensus_ratio": round(consensus_ratio, 4),
        "stance": stance,
        "conviction": conviction,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "total_enabled": total_enabled,
    }


def compute_weighted_arbitration(
    state: dict[str, Any],
    *,
    agent_weights: dict[str, float] | None = None,
    disabled_agents: set[str] | None = None,
    decision_threshold: dict[str, Any] | None = None,
) -> ArbitrationResult:
    """Run weighted convergence arbitration over Tier-0 contracts."""
    signals = compute_agent_weighted_signals(
        state, agent_weights=agent_weights, disabled_agents=disabled_agents
    )
    global_score = compute_global_weighted_score(signals)

    composite = global_score["composite"]
    confidence = global_score["confidence"]
    stance = global_score["stance"]
    consensus_ratio = global_score["consensus_ratio"]

    thr_buy = decision_threshold.get("buy", {}) if decision_threshold else {}
    thr_sell = decision_threshold.get("sell", {}) if decision_threshold else {}
    min_composite_buy = _f(thr_buy.get("min_composite", 60), 60.0) / 100.0
    min_conf_buy = _f(thr_buy.get("min_confidence", 50), 50.0) / 100.0
    max_composite_sell = _f(thr_sell.get("max_composite", 40), 40.0) / 100.0
    min_conf_sell = _f(thr_sell.get("min_confidence", 50), 50.0) / 100.0

    buy_triggered = (
        stance == "bullish" and composite >= min_composite_buy and confidence >= min_conf_buy
    )
    sell_triggered = (
        stance == "bearish" and composite <= max_composite_sell and confidence >= min_conf_sell
    )
    hold_triggered = not buy_triggered and not sell_triggered

    min_factors = 3
    if decision_threshold and "alignment_gating" in decision_threshold:
        ag = decision_threshold["alignment_gating"]
        if isinstance(ag, dict):
            min_factors = int(ag.get("min_factors_for_directional", min_factors))

    enabled_sigs = [s for s in signals if s.enabled]
    total_factor_count = sum(len(s.factor_signals) for s in enabled_sigs)
    alignment_gated = False
    alignment_reason = ""

    if (buy_triggered or sell_triggered) and total_factor_count < min_factors:
        alignment_gated = True
        alignment_reason = (
            f"alignment_gate: {total_factor_count} active factors < {min_factors} minimum. "
            f"Directional requires at least {min_factors} contributing factors."
        )
        hold_triggered = True
        buy_triggered = False
        sell_triggered = False

    reasons: list[str] = []
    if buy_triggered:
        reasons.append(
            f"BUY signal: composite={composite:.3f} >= {min_composite_buy:.2f}, "
            f"confidence={confidence:.3f} >= {min_conf_buy:.2f}"
        )
        reasons.append(
            f"consensus: {global_score['bullish_count']}/{global_score['total_enabled']} agents bullish"
        )
    elif sell_triggered:
        reasons.append(
            f"SELL signal: composite={composite:.3f} <= {max_composite_sell:.2f}, "
            f"confidence={confidence:.3f} >= {min_conf_sell:.2f}"
        )
        reasons.append(
            f"consensus: {global_score['bearish_count']}/{global_score['total_enabled']} agents bearish"
        )
    else:
        reasons.append(
            f"HOLD: stance={stance}, composite={composite:.3f}, confidence={confidence:.3f}"
        )

    if alignment_gated:
        reasons.append(alignment_reason)

    sorted_sigs = sorted(enabled_sigs, key=lambda s: s.weighted_composite, reverse=True)
    top = sorted_sigs[:3]
    for s in top:
        reasons.append(
            f"top_contributor: [{s.agent_id}] {s.label} composite={s.composite:.3f} "
            f"(weight={s.agent_weight:.2f})"
        )

    return ArbitrationResult(
        composite_score=round(composite, 4),
        confidence=round(confidence, 4),
        stance=stance,
        conviction_level=global_score["conviction"],
        reasons=reasons,
        agent_signals=signals,
        consensus_ratio=consensus_ratio,
        buy_triggered=buy_triggered,
        sell_triggered=sell_triggered,
        hold_triggered=hold_triggered,
        alignment_gated=alignment_gated,
        alignment_reason=alignment_reason,
    )


__all__ = [
    "compute_agent_weighted_signals",
    "compute_global_weighted_score",
    "compute_weighted_arbitration",
]
