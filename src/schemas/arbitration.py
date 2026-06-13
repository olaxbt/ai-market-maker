"""Weighted convergence arbitration schemas."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FactorSignal:
    """Single factor evaluation from a Tier-0 contract field."""

    factor_id: str
    agent_id: str
    raw_value: float
    normalized: float
    weight: float
    enabled: bool = True
    source_field: str = ""


@dataclass
class AgentWeightedSignal:
    """Aggregated signal from one agent after factor weighting."""

    agent_id: str
    agent_type: str
    label: str
    composite: float
    raw_composite: float
    agent_weight: float
    weighted_composite: float
    factor_signals: list[FactorSignal] = field(default_factory=list)
    enabled: bool = True
    confidence: float = 0.5
    stance: str = "neutral"


@dataclass
class ArbitrationResult:
    """Final output of the weighted convergence arbitrator."""

    composite_score: float
    confidence: float
    stance: str
    conviction_level: str
    reasons: list[str] = field(default_factory=list)
    agent_signals: list[AgentWeightedSignal] = field(default_factory=list)
    consensus_ratio: float = 0.0
    buy_triggered: bool = False
    sell_triggered: bool = False
    hold_triggered: bool = True
    alignment_gated: bool = False
    alignment_reason: str = ""


AGENT_FACTOR_MAP: dict[str, dict[str, float]] = {
    "1.1": {},
    "1.2": {
        "sentiment_score": 0.28,
        "impact_score": 0.38,
        "event_type": 0.19,
        "narrative_freshness": 0.15,
    },
    "2.1": {
        "setup_score": 0.40,
        "pattern_quality": 0.30,
        "timeframe_align": 0.20,
        "volume_conf": 0.10,
    },
    "2.2": {
        "alpha_signal": 0.50,
        "z_score": 0.25,
        "regime_fit": 0.25,
    },
    "2.3": {
        "rsi": 0.15,
        "macd": 0.20,
        "obv": 0.10,
        "atr": 0.05,
        "adx": 0.15,
        "ema_cross": 0.10,
        "volume": 0.15,
        "pattern_rec": 0.10,
    },
    "3.1": {
        "fomo_level": 0.35,
        "social_volume": 0.25,
        "divergence_warning": 0.40,
    },
    "3.2": {
        "etf_trend": 0.40,
        "funding_rate": 0.30,
        "oi_delta": 0.30,
    },
    "4.1": {
        "dump_probability": 0.50,
        "concentration_pct": 0.25,
        "wallet_flow": 0.25,
    },
    "4.2": {
        "slippage_risk": 0.35,
        "order_imbalance": 0.35,
        "depth_skew": 0.30,
    },
}


AGENT_WEIGHTS_DEFAULT: dict[str, float] = {
    "1.1": 0.05,
    "1.2": 0.05,
    "2.1": 0.25,
    "2.2": 0.10,
    "2.3": 0.30,
    "3.1": 0.05,
    "3.2": 0.05,
    "4.1": 0.05,
    "4.2": 0.15,
}


AGENT_LABEL_MAP: dict[str, str] = {
    "1.1": "Macro Economist",
    "1.2": "News & Narrative",
    "2.1": "Pattern Recognition",
    "2.2": "Statistical Alpha",
    "2.3": "Technical Analysis",
    "3.1": "Retail Hype Tracker",
    "3.2": "Smart Money Tracker",
    "4.1": "Whale Behavior",
    "4.2": "Liquidity & Order Flow",
}


AGENT_TYPE_MAP: dict[str, str] = {
    "1.1": "monetary_sentinel",
    "1.2": "news_narrative_miner",
    "2.1": "pattern_recognition",
    "2.2": "statistical_alpha",
    "2.3": "technical_ta",
    "3.1": "retail_hype",
    "3.2": "pro_bias",
    "4.1": "whale_behavior",
    "4.2": "liquidity_order_flow",
}


__all__ = [
    "AGENT_FACTOR_MAP",
    "AGENT_LABEL_MAP",
    "AGENT_TYPE_MAP",
    "AGENT_WEIGHTS_DEFAULT",
    "AgentWeightedSignal",
    "ArbitrationResult",
    "FactorSignal",
]
