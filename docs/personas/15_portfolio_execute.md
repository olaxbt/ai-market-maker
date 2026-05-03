# Node: Execution Desk (Broker — Order Generation / 執行交易檯)

> **This is a LangGraph node function (`portfolio_execute` / n16), not a standalone agent class.**
> The actual order routing uses `trading.policy_manager.TradingPolicyManager` + `ccxt`.

## Position
Execution layer — the only node that interacts with exchange APIs.

## Goals
- Convert an approved portfolio proposal into a safe, minimal execution plan.
- Execute via CCXT exchange instance (shared across backtest bars to avoid rate limits).

## SOP
1. **Input**: Approved proposal + current portfolio + market data.
2. **Process**: Validate balances → generate orders → submit via CCXT.
3. **Output**: `execution_result` dict with order details and fill status.
4. **Feedback**: Execution result stored in state for Audit node.

## Rules / Constraints
- If Risk Guard did not approve or proposal is empty → return `{"smart_orders": []}`.
- Uses `_CCXT_SHARED` dict to share exchange instances across backtest cycles.
- Order types: prefers post-only limit orders for market-making behaviour.
