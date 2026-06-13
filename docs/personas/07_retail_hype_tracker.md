# Persona: Retail Hype Tracker — Agent 3.1 (零售热度追踪者)

## Position
Tier-0 perception agent that monitors retail trader euphoria/fear cycles. Acts as a contrarian indicator — extreme retail FOMO signals potential tops, while retail despair signals bottoms.

## Agent Classification
- **Agent ID**: 3.1
- **Type**: `retail_hype`
- **Code Class**: `RetailHypeTrackerAgent` (`src/agents/retail_hype_tracker.py`)
- **Enabled by default**: Yes (weight: 0.05)

## Goals
- Measure FOMO/euphoria levels on a 0–100 scale from social and behavioral proxies
- Detect divergence warnings when retail positioning conflicts with price action
- Provide contrarian sentiment extremes to the weighted arbitrator

## SOP
1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context`
2. **Process**:
   - `RetailHypeTrackerAgent.analyze()` evaluates social sentiment, funding rate retail tilt, and volume anomalies
   - Returns `FOMO_Level` (int), `Divergence_Warning` (bool), and `Social_Volume` proxy
3. **Output**:
   - `retail_hype_tracker["primary"]` — analysis for primary ticker
   - `retail_hype_tracker["by_symbol"]` — per-symbol analysis
   - `tier0_contracts` — one entry for agent 3.1
4. **Telemetry**: FlowEvent reasoning entry with FOMO and divergence details

## Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "3.1",
    "ticker": str,
    "status": "success" | "error",
    "FOMO_Level": int,                # [0, 100] retail euphoria
    "Divergence_Warning": bool,       # retail vs price divergence
    "Social_Volume": int              # optional proxy
}
```

## Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `fomo_level` | 0.35 | `FOMO_Level` | Inverted: 100→0, 0→1 (high FOMO = bearish) |
| `social_volume` | 0.25 | Proxy from FOMO × 0.5 | Inverse proxy |
| `divergence_warning` | 0.40 | `Divergence_Warning` | True→0.20, False→0.55 |

## Rules / Constraints
- Contrarian logic: high FOMO is bearish (retail crowded long), low FOMO is bullish (fear/despair)
- Divergence warning at FOMO ≥ 80 triggers a strong bearish tilt in downstream alignment gating
- Stubbed when Nexus data unavailable — returns neutral values
- Combined with Agent 3.2 (Pro Bias) for the full sentiment picture
