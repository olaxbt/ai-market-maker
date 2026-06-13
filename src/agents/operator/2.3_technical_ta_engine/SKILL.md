# Skill: Technical TA Engine (2.3)

## Capabilities
- `analyze(ticker, market_data)` → Tier-0 contract with indicator bundle
- Direct query: "What's the RSI of BTC?"
- Direct query: "Show MACD for ETH"

## Data Sources
- OHLCV bars (configurable period & count)
- Indicator catalog: RSI, MACD, BB, EMA, SMA, ATR, Ichimoku

## Query Interface
```
/technical_ta_engine?ticker=BTC/USDT&period=4h&bars=100
```
Returns: full indicator bundle + status.

## Dependencies
- `ta` Python library or custom indicator implementation
- Exchange OHLCV fetcher
