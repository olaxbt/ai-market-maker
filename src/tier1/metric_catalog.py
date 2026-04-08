"""Authoritative Tier-1 ``metric_id`` registry (Tier-0 contract field mapping).

Use for UI pickers, Architect prompts, and CI drift checks. TA keys mirror
``tools.technical_indicators.indicator_keys()`` (Agent 2.3 ``ta_indicators``).
"""

from __future__ import annotations

from typing import Any

try:
    from tools.technical_indicators import indicator_keys as _indicator_keys
except ImportError:  # optional in minimal envs

    def _indicator_keys() -> tuple[str, ...]:
        return ()


def _ta_metric_rows() -> list[dict[str, Any]]:
    return [
        {
            "metric_id": f"ta_{name}",
            "tier0_agent": "2.3",
            "contract_path": f"ta_indicators.{name}",
            "family": "technical",
        }
        for name in _indicator_keys()
    ]


# Non-TA metrics resolved in ``tier1.resolvers.resolve_metric``.
CORE_METRICS: tuple[dict[str, Any], ...] = (
    {"metric_id": "circuit_breaker_status", "tier0_agent": "1.2", "family": "macro_news"},
    {"metric_id": "black_swan_news", "tier0_agent": "1.2", "family": "macro_news"},
    {"metric_id": "mon_liquidity_score", "tier0_agent": "1.1", "family": "macro"},
    {"metric_id": "mon_macro_regime_state", "tier0_agent": "1.1", "family": "macro"},
    {"metric_id": "news_impact", "tier0_agent": "1.2", "family": "macro_news"},
    {"metric_id": "news_event_type", "tier0_agent": "1.2", "family": "macro_news"},
    {"metric_id": "pattern_setup", "tier0_agent": "2.1", "family": "structure"},
    {"metric_id": "pattern_name", "tier0_agent": "2.1", "family": "structure"},
    {"metric_id": "alpha_z", "tier0_agent": "2.2", "family": "quant"},
    {"metric_id": "alpha_signal_label", "tier0_agent": "2.2", "family": "quant"},
    {"metric_id": "alpha_strong_buy", "tier0_agent": "2.2", "family": "quant"},
    {"metric_id": "alpha_strong_sell", "tier0_agent": "2.2", "family": "quant"},
    {"metric_id": "factor_confluence", "tier0_agent": "2.2", "family": "quant"},
    {"metric_id": "retail_fomo", "tier0_agent": "3.1", "family": "behavioral"},
    {"metric_id": "retail_div", "tier0_agent": "3.1", "family": "behavioral"},
    {"metric_id": "retail_sent_z", "tier0_agent": "3.1", "family": "behavioral"},
    {"metric_id": "pro_bias", "tier0_agent": "3.2", "family": "flow"},
    {"metric_id": "pro_etf_trend", "tier0_agent": "3.2", "family": "flow"},
    {"metric_id": "whale_dump_prob", "tier0_agent": "4.1", "family": "microstructure"},
    {"metric_id": "whale_sell_pressure", "tier0_agent": "4.1", "family": "microstructure"},
    {"metric_id": "liq_slippage", "tier0_agent": "4.2", "family": "microstructure"},
    {"metric_id": "liq_imbalance", "tier0_agent": "4.2", "family": "microstructure"},
    {"metric_id": "liq_poc_price", "tier0_agent": "4.2", "family": "microstructure"},
)


def all_tier1_metrics() -> list[dict[str, Any]]:
    """Flattened catalog: core + ``ta_*`` indicators."""
    return [*CORE_METRICS, *_ta_metric_rows()]


def metric_ids_sorted() -> list[str]:
    return sorted(m["metric_id"] for m in all_tier1_metrics())


__all__ = ["CORE_METRICS", "all_tier1_metrics", "metric_ids_sorted"]
