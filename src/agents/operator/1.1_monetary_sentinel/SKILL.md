# Skill: Monetary Sentinel (1.1)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "What's the current macro regime for BTC?"
- Direct query: "Is there a liquidity crisis signal?"

## Data Sources
- Nexus Global Bundle (macro endpoints)
- CCXT market_data (BTC futures premium)
- DXY/BTC correlation cache

## Query Interface
```
/monetary_sentinel?ticker=BTC/USDT
```
Returns: macro regime state + confidence + reasoning.

## Dependencies
- `NexusDataClient` for global macro feeds
- Falls back to price-only stubs when Nexus is disabled
