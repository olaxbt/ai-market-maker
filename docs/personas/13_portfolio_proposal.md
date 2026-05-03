# Node: Portfolio Proposal (Execution — Allocation / 投資組合提案)

> **This is a LangGraph node function, not a standalone agent class.**

## Position
Execution layer — translates the signal into a concrete allocation proposal.

## Goals
- Convert Signal Arbitrator's stance into a portfolio weight proposal.
- Prioritise capital preservation — most assets stay HOLD.

## SOP
1. **Input**: State with signal, risk context, current holdings.
2. **Process**: Determine desired portfolio weights based on stance + confidence → apply risk constraints → cap single positions.
3. **Output**: Dict with `portfolio_weights`, target positions, reasoning.
4. **Feedback**: None — stateless per-cycle.

## Rules / Constraints
- Proposal is submitted to Risk Guard for approval.
- Max single position ≤ 35% of portfolio.
- Default to HOLD unless strong conviction from signal.
