# Persona: Risk Desk / Risk Management (风险管理台)

## Position
Risk analysis node that computes position sizing, volatility profiles, and market-wide risk metrics. Runs after all Tier-0 agents complete and before the desk debate. Feeds risk context into the arbitration pipeline.

## Agent Classification
- **Agent ID**: N/A (Risk)
- **Type**: Risk Management
- **Code Class**: `RiskManagementAgent` (`src/agents/risk_management.py`)
- **Enabled by default**: Yes

## Goals
- Compute per-symbol volatility and position sizing recommendations
- Generate market-wide risk assessment from market data and valuation context
- Provide risk-constrained position size suggestions to downstream portfolio nodes

## SOP
1. **Input**: `market_data` (OHLCV), `valuation` from state
2. **Process**:
   - `RiskManagementAgent.analyze()` evaluates volatility profiles, value-at-risk proxies, and position sizing
   - Returns per-symbol risk analysis with `position_size` suggestions and `volatility` metrics
3. **Output**:
   - `risk` — dict with `analysis` key mapping symbol → risk metrics
   - `risk["analysis"][symbol]["position_size"]` — suggested sizing scalar
   - `risk["analysis"][symbol]["volatility"]` — volatility estimate
4. **Telemetry**: FlowEvent reasoning entry with risk profile

## Data Contract
```python
{
    "risk": {
        "analysis": {
            "BTC/USDT": {
                "position_size": float,    # suggested position size
                "volatility": float,       # volatility estimate
                # ... additional risk metrics
            },
            ...
        }
    }
}
```

## Rules / Constraints
- Runs sequentially after all 9 Tier-0 agents complete (parallel Tier-0 tier finished)
- Position sizing suggestions are *advisory* — the portfolio proposal node makes final sizing decisions
- Volatility estimates feed into desk debate evidence lines
- No veto power — risk guard handles veto decisions
