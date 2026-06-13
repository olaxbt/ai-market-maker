# Skill: Portfolio Management

## Capabilities
- `get_state()` → portfolio snapshot
- Direct query: "What's my current NAV?"
- Direct query: "Show all open positions"

## Data Sources
- Trade book (in-memory + persistent)
- Execution engine position feed
- Cash balance from exchange/OMS

## Query Interface
```
/portfolio_management?action=state
/portfolio_management?action=positions
```
Returns: portfolio snapshot with NAV, exposure, positions.

## Dependencies
- `trade_book` for position tracking
- Execution engine adapter
