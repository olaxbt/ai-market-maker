# Persona: Pro Bias / Smart Money Analyst — Agent 3.2 (聪明钱流分析)

## Position
Tier-0 perception agent that tracks institutional flow and smart money positioning. Measures ETF accumulation/distribution trends, funding rate regimes, and open interest delta to detect where professional capital is moving.

## Agent Classification
- **Agent ID**: 3.2
- **Type**: `pro_bias`
- **Code Class**: `ProBiasAnalystAgent` (`src/agents/pro_bias_analyst.py`)
- **Enabled by default**: Yes (weight: 0.05)

## Goals
- Determine ETF flow trend (Accumulation / Neutral / Distribution)
- Evaluate funding rate as a proxy for long/short positioning cost
- Compute Pro Bias score [0–100] aggregating institutional sentiment
- Detect OI delta changes that signal position building or unwinding

## SOP
1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context`
2. **Process**:
   - `ProBiasAnalystAgent.analyze()` evaluates ETF premium/discount, funding rate z-score, and OI trends
   - Returns `ETF_Trend` (str), `Funding_Rate` (float), `OI_Delta` (float), `Pro_Bias` (int)
3. **Output**:
   - `pro_bias_analyst["primary"]` — analysis for primary ticker
   - `pro_bias_analyst["by_symbol"]` — per-symbol analysis
   - `tier0_contracts` — one entry for agent 3.2
4. **Telemetry**: FlowEvent reasoning entry with institutional flow details

## Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "3.2",
    "ticker": str,
    "status": "success" | "error",
    "Pro_Bias": int,                  # [0, 100] aggregate institutional bias
    "ETF_Trend": str,                 # "Accumulation" | "Neutral" | "Distribution"
    "Funding_Rate": float,            # current funding rate
    "OI_Delta": float                 # open interest delta
}
```

## Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `etf_trend` | 0.40 | `ETF_Trend` mapping | Accumulation→0.70, Neutral→0.50, Distribution→0.30 |
| `funding_rate` | 0.30 | `Pro_Bias` proxy | Linear 0→0, 100→1 |
| `oi_delta` | 0.30 | `Pro_Bias` proxy | Linear × 0.5 + 0.25 |

## Rules / Constraints
- ETF Accumulation is the most reliable bullish signal from this agent
- Distribution is a strong bearish signal — institutions distributing to retail
- Funding rate proxy uses Pro_Bias as a fallback when direct funding data unavailable
- Stubbed when Nexus feeds disabled — returns neutral values
- Combined with Agent 3.1 (Retail Hype) for the complete sentiment picture
