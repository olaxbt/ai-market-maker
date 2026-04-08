"""Pydantic models for Tier-1 Strategy Blueprint (Architect) and Execution Payload (Applier)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class StrategyMetadata(BaseModel):
    strategy_name: str = Field(alias="Strategy_Name", default="Unnamed")
    target_universe: str = Field(alias="Target_Universe", default="SINGLE_TICKER")
    primary_time_horizon: str = Field(alias="Primary_Time_Horizon", default="swing_trading")

    model_config = {"populate_by_name": True}


class PersonaSignalMix(BaseModel):
    """Optional continuous style knobs; Applier applies a deterministic blend on top of gated alpha."""

    trend_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    momentum_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    mean_revert_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    volume_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    volatility_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    long_bias: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Optional tilt added to long score before min-convergence check.",
    )

    model_config = {"populate_by_name": True}


class PersonaGenetics(BaseModel):
    user_configured_style: str = Field(alias="User_Configured_Style", default="system")
    risk_appetite: Literal["aggressive", "balanced", "defensive", "custom"] = Field(
        alias="Risk_Appetite", default="balanced"
    )
    permitted_directions: list[Literal["LONG", "SHORT"]] = Field(
        alias="Permitted_Directions", default_factory=lambda: ["LONG", "SHORT"]
    )
    persona_signal_mix: PersonaSignalMix | None = Field(default=None, alias="Persona_Signal_Mix")

    model_config = {"populate_by_name": True}


class RollingPyramidLogic(BaseModel):
    enabled: bool = True
    trigger_profit_pct: float = 0.12
    reinvest_pct: float = 0.6
    max_layers: int = 3


class ExecutionRouting(BaseModel):
    max_acceptable_slippage_bps: int = 25
    capacity_check_path: str = ""
    instruction: str = ""


class CapitalDirectives(BaseModel):
    base_leverage_multiplier: float = Field(default=1.0, ge=0.1, le=125.0)
    max_leverage_multiplier: float | None = Field(
        default=None,
        ge=0.1,
        le=125.0,
        description="If set, effective leverage is min(base, max).",
    )
    max_portfolio_risk_per_trade_pct: float = 0.02
    max_total_position_pct: float = Field(default=0.5, ge=0.01, le=1.0)
    rolling_pyramid_logic: RollingPyramidLogic = Field(
        alias="Rolling_Pyramid_Logic", default_factory=RollingPyramidLogic
    )
    execution_routing: ExecutionRouting = Field(
        alias="Execution_Routing", default_factory=ExecutionRouting
    )

    model_config = {"populate_by_name": True}


class VetoRule(BaseModel):
    """Hard gate; if condition true, trading is blocked per ``veto_target``."""

    rule_name: str
    source: str = ""
    path: str = ""  # Architect documentation path
    metric_id: str = ""  # internal resolver (preferred at runtime)
    operator: str = "=="
    threshold: float | str | bool | None = None
    threshold_array: list[Any] | None = Field(default=None, alias="threshold_array")
    veto_target: Literal["ALL", "LONG_ONLY", "SHORT_ONLY"] = "ALL"

    model_config = {"populate_by_name": True}


class AlphaFactor(BaseModel):
    factor_name: str
    source: str = ""
    path: str = ""
    metric_id: str
    operator: str = ">"
    threshold: float | str | bool | None = None
    threshold_array: list[Any] | None = None
    weight_pct: int = Field(ge=5, le=100)
    vote_direction: Literal["LONG", "SHORT", "NEUTRAL"] = "LONG"

    model_config = {"populate_by_name": True}


class PortfolioDeskBridge(BaseModel):
    """Factors merged in :mod:`trading.desk_inputs` into ``quant_analysis`` (same Tier-1 doc as applier)."""

    close_momentum_when_ta_hold: bool = Field(
        default=False,
        alias="Close_Momentum_When_TA_Hold",
        description="If merged TA/stat signal is hold, upgrade to buy on positive OHLCV close drift.",
    )
    close_momentum_lookback_bars: int = Field(
        default=5,
        ge=2,
        le=10_000,
        alias="Close_Momentum_Lookback_Bars",
    )
    close_momentum_min_net_frac: float = Field(
        default=0.0,
        alias="Close_Momentum_Min_Net_Frac",
    )

    model_config = {"populate_by_name": True}


class TacticalParameters(BaseModel):
    veto_layer_constraints: list[VetoRule] = Field(
        alias="Veto_Layer_Constraints", default_factory=list
    )
    min_convergence_score_required: int = Field(
        alias="min_convergence_score_required", default=55, ge=5, le=100
    )
    entry_ease_fraction: float = Field(
        default=0.0,
        ge=0.0,
        le=0.95,
        alias="Entry_Ease_Fraction",
        description="Lowers effective min convergence: effective = round(min_req * (1 - ease)).",
    )
    multi_factor_alpha_matrix: list[AlphaFactor] = Field(
        alias="Multi_Factor_Alpha_Matrix", default_factory=list
    )
    portfolio_desk_bridge: PortfolioDeskBridge = Field(
        default_factory=PortfolioDeskBridge,
        alias="Portfolio_Desk_Bridge",
        description="Optional portfolio quant bridge factors (not Applier veto/alpha math).",
    )

    model_config = {"populate_by_name": True}

    @field_validator("multi_factor_alpha_matrix")
    @classmethod
    def check_factor_count(cls, v: list[AlphaFactor]) -> list[AlphaFactor]:
        if len(v) > 15:
            raise ValueError("Multi_Factor_Alpha_Matrix must have at most 15 factors")
        return v


class StopLossCriteria(BaseModel):
    sl_atr_multiplier: float = 2.0
    sl_fixed_pct: float | None = None
    volatility_anchor_path: str = ""
    instruction: str = ""


class TakeProfitCriteria(BaseModel):
    target_rr_ratio: float = 2.0
    liquidity_target_path: str = ""
    instruction: str = ""


class TrailingStopCriteria(BaseModel):
    enabled: bool = False
    activation_pct: float = Field(default=0.04, ge=0.0, le=0.5)
    instruction: str = ""

    model_config = {"populate_by_name": True}


class MaCrossPeriods(BaseModel):
    enabled: bool = False
    fast_period: int = Field(default=12, ge=1, le=500)
    slow_period: int = Field(default=26, ge=1, le=500)

    model_config = {"populate_by_name": True}


class TradeManagementLogic(BaseModel):
    stop_loss_criteria: StopLossCriteria = Field(
        alias="Stop_Loss_Criteria", default_factory=StopLossCriteria
    )
    take_profit_criteria: TakeProfitCriteria = Field(
        alias="Take_Profit_Criteria", default_factory=TakeProfitCriteria
    )
    trailing_stop: TrailingStopCriteria = Field(
        default_factory=TrailingStopCriteria, alias="Trailing_Stop"
    )
    ma_cross_periods: MaCrossPeriods = Field(
        default_factory=MaCrossPeriods, alias="MA_Cross_Periods"
    )
    dynamic_exit_triggers: dict[str, bool] = Field(
        alias="Dynamic_Exit_Triggers", default_factory=dict
    )

    model_config = {"populate_by_name": True}


class StrategyBlueprint(BaseModel):
    """Trading bible consumed by :mod:`tier1.applier` — weights/rules are not altered by the Applier."""

    strategy_metadata: StrategyMetadata = Field(
        alias="Strategy_Metadata", default_factory=StrategyMetadata
    )
    persona_genetics: PersonaGenetics = Field(
        alias="Persona_Genetics", default_factory=PersonaGenetics
    )
    capital_directives: CapitalDirectives = Field(
        alias="Capital_Directives", default_factory=CapitalDirectives
    )
    tactical_parameters: TacticalParameters = Field(
        alias="Tactical_Parameters", default_factory=TacticalParameters
    )
    trade_management_logic: TradeManagementLogic = Field(
        alias="Trade_Management_Logic", default_factory=TradeManagementLogic
    )

    model_config = {"populate_by_name": True}


class ExecutionRoutingPayload(BaseModel):
    order_type: str = "MARKET"
    entry_price: float | None = None
    position_size_usdt: float = 0.0
    leverage: float = 1.0
    twap_required: bool = False


class StopLossPayload(BaseModel):
    price: float | None = None
    type: str = "STOP_MARKET"
    adjustment_log: str = ""


class TakeProfitPayload(BaseModel):
    price: float | None = None
    type: str = "LIMIT"
    target_hvn_anchor: bool = False


class TrailingStopPayload(BaseModel):
    enabled: bool = False
    activation_pct: float = 0.04
    instruction: str = ""


class MaCrossPayload(BaseModel):
    enabled: bool = False
    fast_period: int = 12
    slow_period: int = 26


class TradeManagementPayload(BaseModel):
    stop_loss: StopLossPayload = Field(default_factory=StopLossPayload)
    take_profit: TakeProfitPayload = Field(default_factory=TakeProfitPayload)
    trailing_stop: TrailingStopPayload = Field(default_factory=TrailingStopPayload)
    ma_cross: MaCrossPayload = Field(default_factory=MaCrossPayload)


class ExecutionPayload(BaseModel):
    """Phase-4 output for exchange / downstream execution."""

    timestamp: str = ""
    symbol: str = ""
    signal: Literal["VETO", "HOLD", "EXECUTE_LONG", "EXECUTE_SHORT"] = "HOLD"
    conviction_score: int = 0
    veto_rule_triggered: str | None = None
    execution_routing: ExecutionRoutingPayload = Field(default_factory=ExecutionRoutingPayload)
    trade_management: TradeManagementPayload = Field(default_factory=TradeManagementPayload)
    blueprint_meta: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = [
    "AlphaFactor",
    "CapitalDirectives",
    "ExecutionPayload",
    "ExecutionRouting",
    "ExecutionRoutingPayload",
    "MaCrossPayload",
    "MaCrossPeriods",
    "PersonaGenetics",
    "PersonaSignalMix",
    "RollingPyramidLogic",
    "StopLossCriteria",
    "StopLossPayload",
    "StrategyBlueprint",
    "StrategyMetadata",
    "TacticalParameters",
    "TakeProfitCriteria",
    "TakeProfitPayload",
    "TradeManagementLogic",
    "TradeManagementPayload",
    "TrailingStopCriteria",
    "TrailingStopPayload",
    "VetoRule",
]
