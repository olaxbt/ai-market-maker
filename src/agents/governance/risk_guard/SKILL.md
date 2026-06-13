# Skill: Risk Guard

## Capabilities
- `validate(signal, portfolio_state)` → risk gate result
- Direct query: "What's my current drawdown?"
- Direct query: "Is it safe to open a new BTC position?"

## Data Sources
- Portfolio state from `portfolio_management`
- `config/fund_policy.py` — fund-level risk limits
- Runtime PnL from execution engine

## Query Interface
```
/risk_guard?ticker=BTC/USDT&side=long&size=0.5
```
Returns: approved/blocked + per-gate flags.

## Dependencies
- `fund_policy` for limits
- Portfolio state estimator
