# Skill: Retail Hype Tracker (3.1)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "Is retail getting euphoric on BTC?"
- Direct query: "Any divergence warning?"

## Data Sources
- Nexus SocialSentiment API
- Funding rate (CEX perpetual futures)
- Twitter/Reddit volume (when available)

## Query Interface
```
/retail_hype_tracker?ticker=BTC/USDT
```
Returns: FOMO level + divergence warning + sentiment z-score.

## Dependencies
- `NexusDataClient` for sentiment endpoints
- Falls back to funding-rate only proxy when Nexus disabled
