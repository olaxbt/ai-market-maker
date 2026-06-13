# Skill: Pattern Recognition Bot (2.1)

## Capabilities
- `analyze(ticker, market_data)` → Tier-0 contract with pattern + setup score
- Direct query: "What pattern is forming on BTC?"
- Direct query: "Where is the support level?"

## Data Sources
- OHLCV bars (internal)
- Pre-computed Kalman filter estimates

## Query Interface
```
/pattern_recognition_bot?ticker=BTC/USDT
```
Returns: setup score + pattern label + support level + reasoning.

## Dependencies
- `src/ta/pattern_engine.py` — pattern detection
- Kalman filter from statistical utilities
