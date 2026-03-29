"""Named strategy presets for Quant + backtest demos (PM-friendly, one-click analysis)."""

from strategies.presets import (
    DEFAULT_QUANT_STRATEGY_ID,
    StrategyPreset,
    get_preset,
    list_presets,
    merge_preset_quick_request,
    quant_trace_meta,
)

__all__ = [
    "DEFAULT_QUANT_STRATEGY_ID",
    "StrategyPreset",
    "get_preset",
    "list_presets",
    "merge_preset_quick_request",
    "quant_trace_meta",
]
