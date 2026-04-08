"""Named strategy blueprints (menu). JSON-serializable via ``StrategyBlueprint.model_dump``."""

from __future__ import annotations

from tier1.models import (
    AlphaFactor,
    CapitalDirectives,
    ExecutionRouting,
    PersonaGenetics,
    PortfolioDeskBridge,
    RollingPyramidLogic,
    StrategyBlueprint,
    StrategyMetadata,
    TacticalParameters,
    TradeManagementLogic,
    VetoRule,
)

_PRESET_REGISTRY: dict[str, StrategyBlueprint] = {}


def _register(name: str, bp: StrategyBlueprint) -> StrategyBlueprint:
    _PRESET_REGISTRY[name.lower()] = bp
    return bp


def list_presets() -> list[str]:
    return sorted(_PRESET_REGISTRY.keys())


def get_preset(name: str) -> StrategyBlueprint:
    key = (name or "").strip().lower()
    if key not in _PRESET_REGISTRY:
        raise KeyError(f"unknown_tier1_preset:{name!r} (try {list_presets()})")
    return _PRESET_REGISTRY[key]


# Default safety overlay + liquidity toxicity proxy (Tier-0 has no amihud z; use slippage).
def _default_vetoes() -> list[VetoRule]:
    return [
        VetoRule(
            rule_name="DEFAULT SAFETY: Black Swan Circuit Breaker",
            source="1.2 News Narrative Miner",
            path="Agent_1.2.Circuit_Breaker_Status",
            metric_id="circuit_breaker_status",
            operator="==",
            threshold="TRIGGERED - AGGRESSIVE OVERRIDE",
            veto_target="ALL",
        ),
        VetoRule(
            rule_name="Extreme slippage (execution toxicity)",
            source="4.2 Liquidity & Order Flow",
            path="Agent_4.2.Slippage_Risk_Score",
            metric_id="liq_slippage",
            operator=">=",
            threshold=95,
            veto_target="ALL",
        ),
    ]


BALANCED = _register(
    "balanced",
    StrategyBlueprint(
        strategy_metadata=StrategyMetadata(
            Strategy_Name="AIMM Tier-1 Balanced",
            Target_Universe="PRESET_BALANCED",
            Primary_Time_Horizon="swing_trading",
        ),
        persona_genetics=PersonaGenetics(
            User_Configured_Style="balanced_hybrid",
            Risk_Appetite="balanced",
            Permitted_Directions=["LONG", "SHORT"],
        ),
        capital_directives=CapitalDirectives(
            base_leverage_multiplier=1.5,
            max_portfolio_risk_per_trade_pct=0.02,
            max_total_position_pct=0.45,
            rolling_pyramid_logic=RollingPyramidLogic(
                enabled=True, trigger_profit_pct=0.12, reinvest_pct=0.5, max_layers=3
            ),
            execution_routing=ExecutionRouting(
                max_acceptable_slippage_bps=25,
                capacity_check_path="Agent_4.2.liquidity_matrix[{{TARGET_SYMBOL}}].safe_execution_capacity_usdt",
                instruction="If size exceeds safe capacity, use TWAP.",
            ),
        ),
        tactical_parameters=TacticalParameters(
            veto_layer_constraints=_default_vetoes(),
            min_convergence_score_required=50,
            multi_factor_alpha_matrix=[
                AlphaFactor(
                    factor_name="Risk-on macro",
                    source="1.1 Monetary Sentinel",
                    path="Agent_1.1.macro_regime_state",
                    metric_id="mon_macro_regime_state",
                    operator="==",
                    threshold=2,
                    weight_pct=18,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Pattern setup",
                    source="2.1 Pattern Recognition Bot",
                    path="Agent_2.1.Setup_Score",
                    metric_id="pattern_setup",
                    operator=">=",
                    threshold=55,
                    weight_pct=20,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Stat alpha long",
                    source="2.2 Statistical Alpha Engine",
                    path="Agent_2.2.alpha_signal",
                    metric_id="alpha_strong_buy",
                    operator="==",
                    threshold=True,
                    weight_pct=22,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Risk-off macro",
                    source="1.1 Monetary Sentinel",
                    path="Agent_1.1.macro_regime_state",
                    metric_id="mon_macro_regime_state",
                    operator="==",
                    threshold=0,
                    weight_pct=18,
                    vote_direction="SHORT",
                ),
                AlphaFactor(
                    factor_name="Whale dump pressure",
                    source="4.1 Whale Behavior Analyst",
                    path="Agent_4.1.Dump_Probability",
                    metric_id="whale_dump_prob",
                    operator=">=",
                    threshold=0.55,
                    weight_pct=22,
                    vote_direction="SHORT",
                ),
            ],
        ),
        trade_management_logic=TradeManagementLogic(),
    ),
)


AGGRESSIVE = _register(
    "aggressive",
    StrategyBlueprint(
        strategy_metadata=StrategyMetadata(
            Strategy_Name="AIMM Tier-1 Aggressive",
            Target_Universe="PRESET_AGGRESSIVE",
            Primary_Time_Horizon="swing_trading",
        ),
        persona_genetics=PersonaGenetics(
            User_Configured_Style="momentum_overlay",
            Risk_Appetite="aggressive",
            Permitted_Directions=["LONG", "SHORT"],
        ),
        capital_directives=CapitalDirectives(
            base_leverage_multiplier=2.5,
            max_portfolio_risk_per_trade_pct=0.04,
            max_total_position_pct=0.6,
            rolling_pyramid_logic=RollingPyramidLogic(
                enabled=True, trigger_profit_pct=0.10, reinvest_pct=0.6, max_layers=4
            ),
            execution_routing=ExecutionRouting(max_acceptable_slippage_bps=35),
        ),
        tactical_parameters=TacticalParameters(
            veto_layer_constraints=_default_vetoes(),
            min_convergence_score_required=35,
            multi_factor_alpha_matrix=[
                AlphaFactor(
                    factor_name="Risk-on or neutral macro",
                    source="1.1 Monetary Sentinel",
                    metric_id="mon_macro_regime_state",
                    operator=">=",
                    threshold=1,
                    weight_pct=15,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Setup OK",
                    source="2.1 Pattern Recognition Bot",
                    metric_id="pattern_setup",
                    operator=">=",
                    threshold=45,
                    weight_pct=20,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Positive factor z",
                    source="2.2 Statistical Alpha Engine",
                    metric_id="alpha_z",
                    operator=">",
                    threshold=0.0,
                    weight_pct=25,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Pro bid",
                    source="3.2 Pro Bias Analyst",
                    metric_id="pro_bias",
                    operator=">=",
                    threshold=45,
                    weight_pct=20,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Not euphoric retail",
                    source="3.1 Retail Hype Tracker",
                    metric_id="retail_fomo",
                    operator="<",
                    threshold=90,
                    weight_pct=20,
                    vote_direction="LONG",
                ),
            ],
            portfolio_desk_bridge=PortfolioDeskBridge(
                Close_Momentum_When_TA_Hold=True,
                Close_Momentum_Lookback_Bars=5,
                Close_Momentum_Min_Net_Frac=0.0,
            ),
        ),
        trade_management_logic=TradeManagementLogic(),
    ),
)


DEFENSIVE = _register(
    "defensive",
    StrategyBlueprint(
        strategy_metadata=StrategyMetadata(
            Strategy_Name="AIMM Tier-1 Defensive",
            Target_Universe="PRESET_DEFENSIVE",
            Primary_Time_Horizon="swing_trading",
        ),
        persona_genetics=PersonaGenetics(
            User_Configured_Style="capital_preservation",
            Risk_Appetite="defensive",
            Permitted_Directions=["LONG", "SHORT"],
        ),
        capital_directives=CapitalDirectives(
            base_leverage_multiplier=1.0,
            max_portfolio_risk_per_trade_pct=0.01,
            max_total_position_pct=0.25,
            rolling_pyramid_logic=RollingPyramidLogic(
                enabled=False, trigger_profit_pct=0.15, reinvest_pct=0.3, max_layers=2
            ),
            execution_routing=ExecutionRouting(max_acceptable_slippage_bps=15),
        ),
        tactical_parameters=TacticalParameters(
            veto_layer_constraints=_default_vetoes()
            + [
                VetoRule(
                    rule_name="High whale dump probability",
                    source="4.1 Whale Behavior Analyst",
                    metric_id="whale_dump_prob",
                    operator=">=",
                    threshold=0.45,
                    veto_target="LONG_ONLY",
                ),
                VetoRule(
                    rule_name="Retail mania divergence",
                    source="3.1 Retail Hype Tracker",
                    metric_id="retail_div",
                    operator="==",
                    threshold=True,
                    veto_target="LONG_ONLY",
                ),
            ],
            min_convergence_score_required=65,
            multi_factor_alpha_matrix=[
                AlphaFactor(
                    factor_name="Strong risk-on",
                    source="1.1 Monetary Sentinel",
                    metric_id="mon_macro_regime_state",
                    operator="==",
                    threshold=2,
                    weight_pct=20,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="High-quality setup",
                    source="2.1 Pattern Recognition Bot",
                    metric_id="pattern_setup",
                    operator=">=",
                    threshold=65,
                    weight_pct=22,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Institutional accumulation",
                    source="3.2 Pro Bias Analyst",
                    metric_id="pro_etf_trend",
                    operator="==",
                    threshold="Accumulation",
                    weight_pct=18,
                    vote_direction="LONG",
                ),
                AlphaFactor(
                    factor_name="Strong sell alpha",
                    source="2.2 Statistical Alpha Engine",
                    metric_id="alpha_strong_sell",
                    operator="==",
                    threshold=True,
                    weight_pct=20,
                    vote_direction="SHORT",
                ),
                AlphaFactor(
                    factor_name="Risk-off pressure",
                    source="1.1 Monetary Sentinel",
                    metric_id="mon_macro_regime_state",
                    operator="==",
                    threshold=0,
                    weight_pct=20,
                    vote_direction="SHORT",
                ),
            ],
        ),
        trade_management_logic=TradeManagementLogic(),
    ),
)


__all__ = ["AGGRESSIVE", "BALANCED", "DEFENSIVE", "get_preset", "list_presets"]
