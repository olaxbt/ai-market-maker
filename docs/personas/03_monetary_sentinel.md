# Persona: Monetary Sentinel — Agent 1.1 (Macro Economist / 宏观经济学家)

## Position
Tier-0 perception agent that computes macro liquidity regime and systemic beta score for each symbol. Assesses whether market conditions favor risk-on (expansionary liquidity) or risk-off (contractionary) positioning.

## Agent Classification
- **Agent ID**: 1.1
- **Type**: `monetary_sentinel`
- **Code Class**: `MonetarySentinelAgent` (`src/agents/monetary_sentinel.py`)
- **Enabled by default**: Yes (weight: 0.05)

## Goals
- Determine the liquidity regime (risk_on / neutral / risk_off) from market data and optional Nexus context
- Compute a systemic beta score [0–100] indicating macro tail risk
- Provide the weighted arbitrator with macro regime context for all downstream factors

## SOP
1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context` from shared memory
2. **Process**:
   - `MonetarySentinelAgent.analyze()` evaluates OHLCV liquidity proxies (volume depth, spread stability) and Nexus macro endpoints
   - Returns `liquidity_regime` (str) and `systemic_beta_score` (float, 0–100)
3. **Output**:
   - `monetary_sentinel["primary"]` — analysis dict for primary ticker
   - `monetary_sentinel["by_symbol"]` — per-symbol analysis dict
   - `tier0_contracts` — one entry for agent 1.1 via `build_tier0_contract_json()`
4. **Telemetry**: FlowEvent reasoning entry with analysis decision

## Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "1.1",
    "ticker": str,
    "status": "success" | "error",
    "macro_regime_state": 0 | 1 | 2,   # risk_off=0, neutral=1, risk_on=2
    "regime_prob": float,               # [0.01, 0.99] scaled from score
    "Liquidity_Score": int              # [0, 100] rounded systemic beta
}
```

## Factor Map
Agent 1.1 has no configured factors in `AGENT_FACTOR_MAP`. The weight assigner uses a 60/40 blend of regime state and liquidity score as a `macro_bias` factor.

| Factor | Source Field | Normalization |
|--------|-------------|---------------|
| `macro_bias` (implicit) | `macro_regime_state` (60%), `Liquidity_Score` (40%) | Linear map 0→0, 2→1 for regime; 0→0, 100→1 for score |

## Rules / Constraints
- Weight 0.05 — low conviction, acts as context/mood rather than strong signal
- Always enabled — macro regime is a background check for all strategies
- Falls back to neutral/score=50 when Nexus data unavailable
- `regime_prob` clamped to [0.01, 0.99]
