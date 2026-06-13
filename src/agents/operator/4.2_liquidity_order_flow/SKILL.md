# Skill: Liquidity Order Flow Analyst (4.2)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "What's the slippage risk on BTC?"
- Direct query: "Is the order book balanced?"

## Data Sources
- Nexus Depth data (order book snapshots)
- Exchange L2 order book (when available)

## Query Interface
```
/liquidity_order_flow?ticker=BTC/USDT
```
Returns: slippage risk + order imbalance + POC price.

## Dependencies
- `NexusDataClient` depth endpoints
- Falls back to stub estimators when depth data unavailable
