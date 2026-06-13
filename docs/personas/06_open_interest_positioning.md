# Persona: Sentiment & Flow Agents — 3.1 Retail Hype Tracker, 3.2 Pro Bias Analyst (情绪与资金流分析)

## Position
Tier-0 perception cluster covering retail sentiment and institutional/smart-money flow. These agents monitor market psychology extremes (retail euphoria/fear) and professional positioning (ETF flows, funding rates, OI changes) to detect crowd-driven inflection points.

## Agent Classification

| Agent ID | Code ID | Name | Weight | Class |
|----------|---------|------|--------|-------|
| 3.1 | retail_hype_tracker | Retail Hype Tracker | 0.05 | `RetailHypeTrackerAgent` |
| 3.2 | pro_bias_analyst | Pro Bias / Smart Money | 0.05 | `ProBiasAnalystAgent` |

---

### Agent 3.1 — Retail Hype Tracker

**Role**: Behavioral psychologist — measures retail FOMO/euphoria levels and social volume extremes. Detects divergence warnings when crowded retail positioning contradicts price action.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "3.1",
    "ticker": str,
    "status": "success" | "error",
    "FOMO_Level": int,                # [0, 100] retail euphoria metric
    "Divergence_Warning": bool,        # retail positioning vs price divergence
    "Social_Volume": int               # optional social media volume proxy
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `fomo_level` | 0.35 | Inverted `FOMO_Level` | High FOMO = bearish (retail euphoria) |
| `social_volume` | 0.25 | Proxy from FOMO * 0.5 | Inverse proxy |
| `divergence_warning` | 0.40 | `Divergence_Warning` | True→0.20, False→0.55 |

---

### Agent 3.2 — Pro Bias Analyst (Smart Money)

**Role**: Smart money flow tracker — monitors ETF accumulation/distribution trends, funding rate regimes, and open interest (OI) deltas to measure institutional conviction.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "3.2",
    "ticker": str,
    "status": "success" | "error",
    "Pro_Bias": int,                  # [0, 100] professional bias score
    "ETF_Trend": str,                 # "Accumulation" | "Neutral" | "Distribution"
    "Funding_Rate": float,            # Current funding rate
    "OI_Delta": float                 # Open Interest change
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `etf_trend` | 0.40 | `ETF_Trend` mapping | Accumulation→0.70, Neutral→0.50, Distribution→0.30 |
| `funding_rate` | 0.30 | `Pro_Bias` proxy | Linear 0→0, 100→1 |
| `oi_delta` | 0.30 | `Pro_Bias` proxy | Linear 0→0, 100→1 (blended with 0.25 offset) |

## SOP (Both Agents)

1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context`
2. **Process**:
   - 3.1: `RetailHypeTrackerAgent.analyze()` — social volume proxies, FOMO estimation
   - 3.2: `ProBiasAnalystAgent.analyze()` — ETF flow signals, funding rate evaluation
3. **Output**: Each agent writes its node-specific payload and appends one entry to `tier0_contracts`
4. **Telemetry**: FlowEvent reasoning entries per agent

## Rules / Constraints
- Both agents carry weight 0.05 — moderate conviction but not decisive alone
- High FOMO + divergence warning from Agent 3.1 is a strong bearish alignment signal
- ETF Accumulation from Agent 3.2 provides direct institutional conviction proxy
- Both stubbed when Nexus data unavailable
