# Skill: Statistical Alpha Engine (2.2)

## Capabilities
- `analyze(ticker, market_data)` → Tier-0 contract with cross-sectional ranking
- Direct query: "How does BTC rank in the universe?"
- Direct query: "What's the cross-sectional z-score of ETH?"

## Data Sources
- Universe-wide OHLCV (all tracked symbols)
- Factor model cache (momentum, value, volatility, on-chain)

## Query Interface
```
/statistical_alpha_engine?ticker=BTC/USDT
```
Returns: cross-sectional rank + z-score + alpha signal + factor confluence.

## Dependencies
- Universe config from `src/config/default_universe.py`
- Factor computation pipeline (statistical methods)
