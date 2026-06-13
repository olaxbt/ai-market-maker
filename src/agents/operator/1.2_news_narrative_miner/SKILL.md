# Skill: News Narrative Miner (1.2)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "Any breaking news impacting BTC?"
- Direct query: "What's the current narrative phase?"

## Data Sources
- Nexus News API
- News decay timeline (in-memory)

## Query Interface
```
/news_narrative_miner?ticker=BTC/USDT
```
Returns: impact score + event type + decay + reasoning.

## Dependencies
- `NexusDataClient` news endpoints
- Falls back to neutral stubs when Nexus disabled
