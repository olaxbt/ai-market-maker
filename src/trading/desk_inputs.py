"""Bridge Tier-0 graph outputs → legacy shapes the **portfolio desk** already consumes.

The LangGraph stores quant signals under ``technical_ta_engine`` / ``statistical_alpha_engine``,
while :class:`agents.portfolio_management.PortfolioManagementAgent` still reads ``quant_analysis``.
Centralizing the merge here avoids a second graph node and keeps one adapter for execution.

``TA-Lib`` MACD is only filled once OHLCV length ≥ 40 (warm-up in ``technical_indicators``), so
shorter backtests chain **RSI** (extremes only: ≤38 ``buy``, ≥62 ``sell``), **EMA vs SMA**, then
**|ROC| ≥ 1%**—otherwise mid-range RSI was mis-labeled ``sell`` and **flat books never opened**.

**Desk strategy preset** (``AIMM_DESK_STRATEGY_PRESET``): optional research overlays. ``trend_guard``
blocks *new* long quant signals that come only from RSI oversold or ROC bounce unless EMA is
materially above SMA (same threshold as the EMA/SMA ladder). MACD/EMA-trend buys pass through.
This is a standard risk overlay, not a guarantee of profitability.

**Tier-1 portfolio bridge** (``Tactical_Parameters.Portfolio_Desk_Bridge`` in the active blueprint):
optional factors such as **close momentum when TA hold** are configured there—via ``AIMM_STRATEGY_PRESET`` or
``AIMM_STRATEGY_BLUEPRINT_PATH``—not via separate ad-hoc env flags. Defaults keep all bridge factors off.
"""

from __future__ import annotations

import math
import os
from typing import Any, Mapping

from tier1 import effective_portfolio_desk_bridge
from tier1.models import PortfolioDeskBridge

_ALPHA_TO_SIGNAL = {"long_bias": "buy", "short_bias": "sell", "hold": "hold"}

_DESK_PRESET_ENV = "AIMM_DESK_STRATEGY_PRESET"


def _desk_strategy_preset() -> str:
    # Default to a multi-indicator preset that is more stable across regimes.
    raw = (os.getenv(_DESK_PRESET_ENV) or "all_weather").strip().lower()
    return (
        raw
        if raw in ("default", "trend_guard", "trend_follow", "all_weather", "adaptive")
        else "default"
    )


def _adaptive_signal(inds: Mapping[str, Any] | None) -> tuple[str, str]:
    """Adaptive preset: decide which signal logic to trust given regime + trend strength.

    - Strong trend (ADX high): use ``trend_follow`` (EMA/SMA alignment).
    - Weak/sideways (ADX low): prefer mean-revert (RSI/Stoch/BB intuition via TA rule bundle).
    - Unknown/missing: fall back to ``all_weather`` for stability.
    """
    if not isinstance(inds, dict):
        return "hold", "none"

    adx = inds.get("adx")
    try:
        adx_f = float(adx) if adx is not None else float("nan")
    except (TypeError, ValueError):
        adx_f = float("nan")

    # If indicators are incomplete, use all_weather.
    if adx_f != adx_f:  # NaN check
        return _all_weather_signal(inds)

    # Trend strength thresholds (common heuristic).
    strong_trend = adx_f >= 25.0
    weak_trend = adx_f <= 18.0

    if strong_trend:
        base_sig, _src = _ta_rule_signal_and_source(inds)
        sig = _trend_follow_override(base_sig, inds)
        return sig, "adaptive_trend_follow"

    if weak_trend:
        sig, src = _ta_rule_signal_and_source(inds)
        # In chop, don't chase EMA/SMA flips; keep the raw micro-signal.
        return sig, f"adaptive_{src}"

    # Middle ground: all_weather.
    return _all_weather_signal(inds)


def _all_weather_signal(inds: Mapping[str, Any] | None) -> tuple[str, str]:
    """Multi-indicator signal (buy/sell/hold, source_tag) using EMA/SMA + MACD + ADX + RSI.

    Goal: avoid buying downtrends and avoid overreacting in low-trend noise.
    """
    if not isinstance(inds, dict):
        return "hold", "none"

    regime = _ema_sma_regime(inds)
    adx = inds.get("adx")
    rsi = inds.get("rsi")
    macd = inds.get("macd")
    macd_sig = inds.get("macd_signal")

    adx_f: float | None = None
    try:
        adx_f = float(adx) if adx is not None else None
        if adx_f is not None and math.isnan(adx_f):
            adx_f = None
    except (TypeError, ValueError):
        adx_f = None

    rsi_f: float | None = None
    try:
        rsi_f = float(rsi) if rsi is not None else None
        if rsi_f is not None and math.isnan(rsi_f):
            rsi_f = None
    except (TypeError, ValueError):
        rsi_f = None

    macd_ok = macd is not None and macd_sig is not None
    if macd_ok:
        try:
            m = float(macd)
            ms = float(macd_sig)
            if not math.isnan(m) and not math.isnan(ms):
                trending = (adx_f is None) or (adx_f >= 20.0)
                if regime == "up" and trending and m > ms:
                    return "buy", "ema_macd_adx"
                if regime == "down" and trending and m < ms:
                    return "sell", "ema_macd_adx"
        except (TypeError, ValueError):
            pass

    # RSI extremes only, gated by regime so we don't knife-catch in downtrends.
    if rsi_f is not None:
        if rsi_f <= 30.0 and regime in ("up", "flat", "unknown"):
            return "buy", "rsi_extreme"
        if rsi_f >= 70.0 and regime in ("down", "flat"):
            return "sell", "rsi_extreme"

    # Fallback to the existing TA ladder.
    sig, src = _ta_rule_signal_and_source(inds)
    if sig != "hold":
        return sig, src
    return "hold", "none"


def _ohlcv_for_ticker(state: Mapping[str, Any], ticker: str) -> list[Any]:
    md = state.get("market_data")
    if not isinstance(md, dict):
        return []
    row = md.get(ticker)
    if not isinstance(row, dict):
        return []
    o = row.get("ohlcv")
    return o if isinstance(o, list) else []


def _close_momentum_frac(ohlcv: list[Any], lookback_bars: int) -> float | None:
    if len(ohlcv) < 2:
        return None
    lb = max(2, int(lookback_bars))
    n = len(ohlcv)
    i0 = max(0, n - lb)
    try:
        c0 = float(ohlcv[i0][4])
        c1 = float(ohlcv[-1][4])
    except (IndexError, TypeError, ValueError):
        return None
    if c0 <= 0:
        return None
    return (c1 / c0) - 1.0


def _ema_confirms_uptrend(inds: Mapping[str, Any] | None) -> bool:
    """True if EMA materially above SMA; True when data missing (do not block for lack of TA)."""
    if not isinstance(inds, dict):
        return True
    ema, sma = inds.get("ema"), inds.get("sma")
    if ema is None or sma is None:
        return True
    try:
        e, s = float(ema), float(sma)
        if math.isnan(e) or math.isnan(s) or s <= 0:
            return True
        return e > s * 1.0002
    except (TypeError, ValueError):
        return True


def _apply_trend_guard_to_buy(signal: str, source: str, inds: Mapping[str, Any] | None) -> str:
    if signal != "buy":
        return signal
    if source in ("macd", "ema_sma"):
        return signal
    if source in ("rsi", "roc") and not _ema_confirms_uptrend(inds):
        return "hold"
    return signal


def _trend_follow_override(signal: str, inds: Mapping[str, Any] | None) -> str:
    """Regime alignment: when EMA/SMA is decisive, prefer its direction over noisy micro-signals."""
    if not isinstance(inds, dict):
        return signal
    ema, sma = inds.get("ema"), inds.get("sma")
    if ema is None or sma is None:
        return signal
    try:
        e, s = float(ema), float(sma)
        if math.isnan(e) or math.isnan(s) or s <= 0:
            return signal
        if e > s * 1.0002:
            return "buy"
        if e < s * 0.9998:
            return "sell"
        return signal
    except (TypeError, ValueError):
        return signal


def _ema_sma_regime(inds: Mapping[str, Any] | None) -> str:
    """Coarse regime label from EMA vs SMA: up/down/flat/unknown."""
    if not isinstance(inds, dict):
        return "unknown"
    ema, sma = inds.get("ema"), inds.get("sma")
    if ema is None or sma is None:
        return "unknown"
    try:
        e, s = float(ema), float(sma)
        if math.isnan(e) or math.isnan(s) or s <= 0:
            return "unknown"
        if e > s * 1.0002:
            return "up"
        if e < s * 0.9998:
            return "down"
        return "flat"
    except (TypeError, ValueError):
        return "unknown"


def _tier0_primary(state: Mapping[str, Any], node_key: str) -> dict[str, Any]:
    blk = state.get(node_key)
    if not isinstance(blk, dict):
        return {}
    p = blk.get("primary")
    return p if isinstance(p, dict) else {}


def _tier0_for_symbol(state: Mapping[str, Any], node_key: str, symbol: str) -> dict[str, Any]:
    """Tier-0 node output for ``symbol`` when ``by_symbol`` exists (multi-asset graph); else primary."""
    blk = state.get(node_key)
    if not isinstance(blk, dict):
        return {}
    bys = blk.get("by_symbol")
    if isinstance(bys, dict):
        row = bys.get(symbol)
        if isinstance(row, dict):
            return row
    p = blk.get("primary")
    return p if isinstance(p, dict) else {}


def _ta_rule_signal_and_source(inds: Mapping[str, Any] | None) -> tuple[str, str]:
    """Return (signal, source_tag) for preset logic; source is macd|rsi|ema_sma|roc|none."""
    if not isinstance(inds, dict):
        return "hold", "none"
    m, ms = inds.get("macd"), inds.get("macd_signal")
    if m is not None and ms is not None:
        try:
            mf, sf = float(m), float(ms)
            if not math.isnan(mf) and not math.isnan(sf):
                if mf > sf:
                    return "buy", "macd"
                if mf < sf:
                    return "sell", "macd"
                return "hold", "macd_flat"
        except (TypeError, ValueError):
            pass

    rsi = inds.get("rsi")
    if rsi is not None:
        try:
            r = float(rsi)
            if not math.isnan(r):
                if r >= 62.0:
                    return "sell", "rsi"
                if r <= 38.0:
                    return "buy", "rsi"
        except (TypeError, ValueError):
            pass

    ema, sma = inds.get("ema"), inds.get("sma")
    if ema is not None and sma is not None:
        try:
            e, s = float(ema), float(sma)
            if not math.isnan(e) and not math.isnan(s) and s > 0:
                if e > s * 1.0002:
                    return "buy", "ema_sma"
                if e < s * 0.9998:
                    return "sell", "ema_sma"
        except (TypeError, ValueError):
            pass

    roc = inds.get("roc")
    if roc is not None:
        try:
            z = float(roc)
            if not math.isnan(z) and abs(z) >= 1.0:
                if z > 0:
                    return "buy", "roc"
                if z < 0:
                    return "sell", "roc"
        except (TypeError, ValueError):
            pass

    return "hold", "none"


def _ta_rule_signal(inds: Mapping[str, Any] | None) -> str:
    """Discrete buy/sell/hold from the TA bundle (MACD when warm, else RSI / ROC)."""
    sig, _src = _ta_rule_signal_and_source(inds)
    return sig


def quant_analysis_for_portfolio(
    state: Mapping[str, Any],
    ticker: str,
    *,
    desk_bridge: PortfolioDeskBridge | None = None,
) -> dict[str, Any]:
    """Return a ``quant_analysis``-shaped dict with ``analysis[ticker].macd_signal`` populated.

    ``desk_bridge`` comes from the active Tier-1 blueprint's ``Portfolio_Desk_Bridge`` when omitted
    (``effective_portfolio_desk_bridge``). Pass explicitly in tests or when batching symbols to avoid
    repeated blueprint loads.
    """
    explicit = state.get("quant_analysis")
    if isinstance(explicit, dict):
        inner = explicit.get("analysis")
        if isinstance(inner, dict) and isinstance(inner.get(ticker), dict):
            return explicit

    bridge = desk_bridge if desk_bridge is not None else effective_portfolio_desk_bridge()

    sig = "hold"
    sources: list[str] = []
    preset = _desk_strategy_preset()
    ta = _tier0_for_symbol(state, "technical_ta_engine", ticker)
    ta_inds: Mapping[str, Any] = {}
    if str(ta.get("status") or "") == "success":
        raw_inds = ta.get("ta_indicators")
        ta_inds = raw_inds if isinstance(raw_inds, dict) else {}
        if preset == "adaptive":
            ta_sig, ta_src = _adaptive_signal(ta_inds)
        elif preset == "all_weather":
            ta_sig, ta_src = _all_weather_signal(ta_inds)
        else:
            ta_sig, ta_src = _ta_rule_signal_and_source(ta_inds)
            if preset == "trend_follow":
                ta_sig = _trend_follow_override(ta_sig, ta_inds)
            if preset == "trend_guard":
                ta_sig = _apply_trend_guard_to_buy(ta_sig, ta_src, ta_inds)
        if ta_sig != "hold":
            sig = ta_sig
            sources.append("technical_ta_engine")

    if sig == "hold":
        sa = _tier0_for_symbol(state, "statistical_alpha_engine", ticker)
        if str(sa.get("status") or "") == "success":
            raw = str(sa.get("alpha_signal") or "hold").lower()
            mapped = _ALPHA_TO_SIGNAL.get(raw, "hold")
            if mapped == "buy" and preset == "trend_guard" and not _ema_confirms_uptrend(ta_inds):
                mapped = "hold"
            if mapped != "hold":
                sig = mapped
                sources.append("statistical_alpha_engine")

    if sig == "hold" and bridge.close_momentum_when_ta_hold:
        ohlcv = _ohlcv_for_ticker(state, ticker)
        mom = _close_momentum_frac(ohlcv, bridge.close_momentum_lookback_bars)
        min_f = float(bridge.close_momentum_min_net_frac)
        if mom is not None and mom >= min_f:
            allow_mom = True
            if preset == "trend_guard" and not _ema_confirms_uptrend(ta_inds):
                allow_mom = False
            if allow_mom:
                sig = "buy"
                sources.append("close_momentum")

    out_analysis: dict[str, Any] = {
        "macd_signal": sig,
        "desk_sources": sources,
    }
    if preset != "default":
        out_analysis["desk_strategy_preset"] = preset
    if ta_inds:
        out_analysis["ema_sma_regime"] = _ema_sma_regime(ta_inds)

    return {
        "status": "success",
        "analysis": {
            ticker: out_analysis,
        },
    }


__all__ = ["quant_analysis_for_portfolio"]
