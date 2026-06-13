# Skill: Pro Bias Analyst (3.2)

## Capabilities
- `analyze(ticker, market_data, nexus_context)` → Tier-0 contract
- Direct query: "Is smart money buying or selling BTC?"
- Direct query: "What's the ETF flow trend?"

## Data Sources
- Nexus ETF endpoints
- Futures basis (perpetual vs spot premium)
- Options skew (25-delta risk reversal)

## Query Interface
```
/pro_bias_analyst?ticker=BTC/USDT
```
Returns: pro bias score + ETF trend + ema slope.

## Dependencies
- `NexusDataClient` for ETF + options data
- Falls back to basis-only analysis when Nexus disabled
