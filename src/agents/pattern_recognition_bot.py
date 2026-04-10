from __future__ import annotations

from typing import Any, Dict

from nexus_data.payload_extract import first_float, technical_analysis_core


def _ohlcv_len(market_data: Any, ticker: str) -> int:
    if not isinstance(market_data, dict):
        return 0
    blob = market_data.get(ticker)
    if not isinstance(blob, dict):
        return 0
    ohlcv = blob.get("ohlcv")
    return len(ohlcv) if isinstance(ohlcv, list) else 0


def _tech_block(nexus_context: dict[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    if not isinstance(nexus_context, dict):
        return None
    ps = nexus_context.get("per_symbol") or {}
    bys = ps.get("by_symbol") if isinstance(ps, dict) else None
    if not isinstance(bys, dict):
        return None
    sym_payload = bys.get(ticker)
    if not isinstance(sym_payload, dict):
        return None
    ta = sym_payload.get("technical_analysis")
    return ta if isinstance(ta, dict) else None


class PatternRecognitionBotAgent:
    """Tier-0 AIMM: denoise + dynamic S/R + breakout timing (technical)."""

    name = "pattern_recognition_bot"
    role = "geometry_and_signal_technician"

    def analyze(
        self,
        *,
        ticker: str,
        market_data: Dict[str, Any],
        nexus_context: dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        n = _ohlcv_len(market_data, ticker)
        ta = _tech_block(nexus_context, ticker)
        nexus_ok = bool(ta and ta.get("ok"))
        raw = ta.get("data") if nexus_ok else None
        conf = 50.0 if n >= 15 else 0.0
        regime = "unknown" if n < 15 else "range"
        mood = None
        pattern_name = None
        support = None
        resistance = None
        pattern_start = None
        pattern_end = None

        if isinstance(raw, dict):
            analysis = technical_analysis_core(raw)
            if analysis:
                mood = analysis.get("mood") or analysis.get("signal")
                pattern_name = (
                    analysis.get("pattern")
                    or analysis.get("pattern_name")
                    or analysis.get("macro_regime")
                    or analysis.get("geometry")
                )
                if isinstance(pattern_name, dict):
                    pattern_name = pattern_name.get("name") or pattern_name.get("type")
                conf = min(
                    95.0,
                    conf
                    + first_float(
                        analysis,
                        "setup_confidence_score",
                        "Setup_Score",
                        "confidence",
                        default=20.0,
                    ),
                )
                regime = mood if isinstance(mood, str) else str(pattern_name or "trend")
                coords = analysis.get("coordinates") or analysis.get("support_resistance")
                if isinstance(coords, dict):
                    support = coords.get("support") or coords.get("support_price")
                    resistance = coords.get("resistance") or coords.get("resistance_price")
                if support is None:
                    for k in ("kalman_support", "support", "support_price"):
                        if k in analysis and analysis[k] is not None:
                            try:
                                support = float(analysis[k])
                            except (TypeError, ValueError):
                                pass
                            break
                if resistance is None:
                    for k in ("resistance", "resistance_price"):
                        if k in analysis and analysis[k] is not None:
                            try:
                                resistance = float(analysis[k])
                            except (TypeError, ValueError):
                                pass
                            break
                pattern_start = analysis.get("pattern_start_time") or analysis.get("pattern_start")
                pattern_end = analysis.get("pattern_end_time") or analysis.get("pattern_end")

        return {
            "status": "success" if (n or nexus_ok) else "error",
            "setup_confidence_score": conf,
            "macro_regime": regime if isinstance(regime, str) else "trend",
            "pattern": pattern_name if pattern_name is not None else regime,
            "support_resistance": {"support": support, "resistance": resistance},
            "inputs": {
                "ohlcv_candles": n,
                "nexus_technical": nexus_ok,
                "mood": mood,
                "pattern_start_time": pattern_start,
                "pattern_end_time": pattern_end,
            },
        }
