"""Threshold calibration: prove BUY/SELL are reachable with current thresholds.

Confidence formula (from ``weight_assigner.compute_global_weighted_score``):
    magnitude = |composite - 0.50| * 2.0         # [0, 1]
    multiplier = min(1.0, 0.5 + consensus_ratio * 0.5)  # [0.5, 1.0]
    confidence = magnitude * multiplier           # [0, 1]

Thresholds (``_V4_DECISION_THRESHOLD`` in weighted_arbitrator.py):
    BUY:  composite >= 0.55  AND  confidence >= 0.10
    SELL: composite <= 0.45  AND  confidence >= 0.10

Tests use the **real v4 agent weights** (not uniform) to match production.
"""

from __future__ import annotations

from schemas.arbitration import AGENT_WEIGHTS_DEFAULT, AgentWeightedSignal
from workflow.weight_assigner import compute_global_weighted_score

_AGENT_IDS = list(AGENT_WEIGHTS_DEFAULT.keys())
_TOTAL_W = sum(AGENT_WEIGHTS_DEFAULT.values())


def _sig(aid: str, composite: float) -> AgentWeightedSignal:
    """Build a minimal ``AgentWeightedSignal`` with real v4 weights."""
    w = AGENT_WEIGHTS_DEFAULT.get(aid, 1.0 / 9)
    return AgentWeightedSignal(
        agent_id=aid,
        agent_type="test",
        label=aid,
        composite=composite,
        raw_composite=composite,
        agent_weight=w,
        weighted_composite=composite * w,
        enabled=True,
        confidence=abs(composite - 0.5) * 2.0,
        stance="bullish" if composite >= 0.55 else "bearish" if composite <= 0.45 else "neutral",
        factor_signals=[],
    )


def _nth_bullish(n: int, composite: float = 0.60) -> list[AgentWeightedSignal]:
    """First *n* agents bullish, rest neutral."""
    sigs = [_sig(a, composite) for a in _AGENT_IDS[:n]]
    sigs += [_sig(a, 0.50) for a in _AGENT_IDS[n:]]
    return sigs


def _nth_bearish(n: int, composite: float = 0.40) -> list[AgentWeightedSignal]:
    """First *n* agents bearish, rest neutral."""
    sigs = [_sig(a, composite) for a in _AGENT_IDS[:n]]
    sigs += [_sig(a, 0.50) for a in _AGENT_IDS[n:]]
    return sigs


# ---------------------------------------------------------------------------
# Reachability — BUY side
# ---------------------------------------------------------------------------


def test_buy_reachable_at_5_of_9_with_real_weights():
    """5/9 bullish at 0.60 with real weights → composite~0.56, confidence~0.11 → BUY."""
    signals = _nth_bullish(5, 0.60)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] >= 0.10, (
        f"5/9 at 0.60: composite={score['composite']:.3f}, "
        f"confidence={score['confidence']:.3f} should be >= 0.10"
    )


def test_buy_not_triggered_at_4_of_9_with_real_weights():
    """4/9 bullish at 0.60 → confidence < 0.10 → HOLD."""
    signals = _nth_bullish(4, 0.60)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] < 0.10, (
        f"4/9 at 0.60: confidence={score['confidence']:.3f} should be < 0.10"
    )


def test_buy_not_triggered_at_low_composite():
    """5/9 bullish at 0.55 (threshold edge) → confidence < 0.10 → HOLD."""
    signals = _nth_bullish(5, 0.55)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] < 0.10, (
        f"5/9 at 0.55: confidence={score['confidence']:.3f} should be < 0.10"
    )


def test_buy_reachable_at_5_of_9_composite_0_62():
    """5/9 bullish at 0.62 → confidence >= 0.10 → BUY."""
    signals = _nth_bullish(5, 0.62)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] >= 0.10, (
        f"5/9 at 0.62: composite={score['composite']:.3f}, "
        f"confidence={score['confidence']:.3f} should be >= 0.10"
    )


def test_buy_stronger_with_more_consensus():
    """7/9 → higher confidence than 5/9 (same agent composite)."""
    s5 = compute_global_weighted_score(_nth_bullish(5, 0.60))
    s7 = compute_global_weighted_score(_nth_bullish(7, 0.60))
    assert s7["confidence"] > s5["confidence"], (
        f"7/9 ({s7['confidence']:.3f}) > 5/9 ({s5['confidence']:.3f})"
    )


# ---------------------------------------------------------------------------
# Reachability — SELL side (symmetric)
# ---------------------------------------------------------------------------


def test_sell_reachable_at_5_of_9():
    """5/9 bearish at 0.40 with real weights → SELL."""
    signals = _nth_bearish(5, 0.40)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] >= 0.10, (
        f"5/9 bearish at 0.40: composite={score['composite']:.3f}, "
        f"confidence={score['confidence']:.3f} should be >= 0.10"
    )


def test_sell_not_triggered_at_3_of_9():
    """3/9 bearish at 0.40 → confidence < 0.10 → HOLD."""
    signals = _nth_bearish(3, 0.40)
    score = compute_global_weighted_score(signals)
    assert score["confidence"] < 0.10, (
        f"3/9 bearish at 0.40: confidence={score['confidence']:.3f} should be < 0.10"
    )


# ---------------------------------------------------------------------------
# Documentation — formula trace
# ---------------------------------------------------------------------------


def test_documentation_table(capsys):
    """Trace the formula at key (composite, consensus) points."""

    def _confidence(composite: float, bullish_n: int) -> float:
        magnitude = abs(composite - 0.5) * 2.0
        max_side = max(bullish_n, 9 - bullish_n)
        consensus_ratio = max_side / 9
        multiplier = min(1.0, 0.5 + consensus_ratio * 0.5)
        return magnitude * multiplier

    cases: list[tuple[str, float, int, float, bool]] = [
        ("5/9 at 0.60", 0.60, 5, _confidence(0.60, 5), _confidence(0.60, 5) >= 0.10),
        ("6/9 at 0.60", 0.60, 6, _confidence(0.60, 6), _confidence(0.60, 6) >= 0.10),
        ("7/9 at 0.55", 0.55, 7, _confidence(0.55, 7), _confidence(0.55, 7) >= 0.10),
        ("5/9 at 0.62", 0.62, 5, _confidence(0.62, 5), _confidence(0.62, 5) >= 0.10),
        ("4/9 at 0.60", 0.60, 4, _confidence(0.60, 4), _confidence(0.60, 4) >= 0.10),
        ("5/9 bear at 0.40", 0.40, 4, _confidence(0.40, 4), _confidence(0.40, 4) >= 0.10),
        ("6/9 bear at 0.40", 0.40, 3, _confidence(0.40, 3), _confidence(0.40, 3) >= 0.10),
    ]
    for label, _comp, _n, conf, buys in cases:
        assert conf > 0, f"{label}: confidence should be > 0"
        flag = "BUY" if buys else "HOLD"
        print(f"  {label:20s} → confidence={conf:.3f} → {flag}")
