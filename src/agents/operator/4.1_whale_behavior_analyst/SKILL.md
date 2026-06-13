# Skill: Whale Behavior Analyst (4.1)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "Are whales dumping BTC?"
- Direct query: "What's the exchange flow balance?"

## Data Sources
- Nexus On-Chain endpoints (whale tx, exchange flow)
- Large transaction monitoring

## Query Interface
```
/whale_behavior_analyst?ticker=BTC/USDT
```
Returns: sell pressure gauge + dump probability + dry powder alert.

## Dependencies
- `NexusDataClient` on-chain endpoints
- Opt-in only: disabled by default in weights
