# Persona: News & Narrative Miner — Agent 1.2 (新闻叙事挖掘者)

## Position
Tier-0 perception agent that evaluates event-driven impact and narrative freshness. Scores headline risk on a breaker scale and classifies event type (Routine → Black Swan) to measure narrative-driven market shocks.

## Agent Classification
- **Agent ID**: 1.2
- **Type**: `news_narrative_miner`
- **Code Class**: `NewsNarrativeMinerAgent` (`src/agents/news_narrative_miner.py`)
- **Enabled by default**: Yes (weight: 0.05)

## Goals
- Compute a breaker score [0–100] measuring news impact magnitude
- Classify the event type into severity buckets (Routine / Elevated / Major Catalyst / Black Swan)
- Track narrative freshness/decay to avoid stale catalyst pricing

## SOP
1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context` from shared memory
2. **Process**:
   - `NewsNarrativeMinerAgent.analyze()` evaluates Nexus news/narrative endpoints and market data for sudden volatility shifts
   - Returns `breaker_score` (float) and `decay_factor` (float, narrative freshness half-life)
3. **Output**:
   - `news_narrative_miner["primary"]` — analysis dict for primary ticker
   - `news_narrative_miner["by_symbol"]` — per-symbol analysis dict
   - `tier0_contracts` — one entry for agent 1.2 via `build_tier0_contract_json()`
4. **Telemetry**: FlowEvent reasoning entry with analysis decision

## Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "1.2",
    "ticker": str,
    "status": "success" | "error",
    "News_Impact_Score": int,         # [0, 100] rounded breaker_score
    "Event_Type": str,                # "Routine" | "Elevated" | "Major Catalyst" | "Black Swan"
    "decay_factor": float | None      # narrative freshness decay
}
```

Event Type thresholds:
| Impact Score | Event Type |
|-------------|------------|
| < 25 | Routine |
| 25–44 | Elevated |
| 45–74 | Major Catalyst |
| ≥ 75 | Black Swan |

## Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `sentiment_score` | 0.28 | Inverted `News_Impact_Score` | High impact → bearish (low score) |
| `impact_score` | 0.38 | Inverted `News_Impact_Score` | Same as sentiment_score |
| `event_type` | 0.19 | `Event_Type` mapping | Routine→0.55, Elevated→0.45, Major→0.35, Black Swan→0.15 |
| `narrative_freshness` | 0.15 | Default 0.5 | Not in contract fields |

## Rules / Constraints
- Weight 0.05 — news context is background noise, not a strong signal
- Inverted impact logic: high news impact = bearish (uncertainty shock)
- Black Swan events force near-zero bullish factor signal
- `decay_factor` may be None if narrative freshness not tracked
