# Persona: Portfolio Execute & Audit (执行与审计)

## Position
Terminal execution and audit node. `portfolio_execute` places the approved trade via the execution adapter (CCXT / Nexus). Skips if vetoed. `audit` assembles the final summary of the entire run for logging and post-run analysis.

## Agent Classification
- **Agent ID**: N/A (Execution / Audit)
- **Type**: Execution & Audit
- **Code Class**: `PortfolioManagementAgent` + `portfolio_execute` / `audit` node functions
- **Enabled by default**: Yes

## Goals
- Place trades through the exchange adapter when not vetoed
- Handle LLM execution fallback (LLM → deterministic)
- Build final run summary with all key decisions, risk status, and execution results
- Maintain paper account snapshot in shared memory for backtest continuity

## SOP

### Portfolio Execute
1. **Input**: `is_vetoed`, `ticker`, `proposal`, `trade_intent`, `market_data`, `run_mode`, `shared_memory`
2. **Process**:
   - If `is_vetoed`: return empty (skip — should not be reached via routing, but safe check)
   - If `llm_mode_enabled()`: call `llm_portfolio_execute()` — fallback to deterministic agent on failure
   - Deterministic: `PortfolioManagementAgent.analyze()` with `execute=True`
   - Paper mode: update paper account snapshot after execution
3. **Output**:
   - `execution_result` — order status, filled quantity, slippage, order IDs
   - `shared_memory["paper"]` — updated paper account snapshot (paper mode)

### Audit
4. **Input**: Full state after execution (or after veto skip)
5. **Process**:
   - Compact final summary of ticker, run_mode, veto status, risk report, execution result, proposal status
   - Build reasoning log entry with summary
6. **Output**:
   - `reasoning_logs` — final audit reasoning entry
   - No new state mutations (read-only analysis)

## Data Contract
```python
# execution_result
{
    "status": "success" | "skipped" | "error",
    "orders": [
        {
            "symbol": str,
            "side": "buy" | "sell",
            "qty": float,
            "filled_qty": float,
            "price": float | None,
            "slippage_bps": float,
            "status": "filled" | "partial" | "rejected"
        }
    ],
    "meta": {
        "source": "portfolio_execute" | "llm_portfolio_execute"
    }
}

# audit reasoning entry
{
    "summary": {
        "ticker": str,
        "run_mode": str,
        "is_vetoed": bool,
        "veto_reason": str,
        "risk_status": str,
        "execution_status": str,
        "proposal_status": str,
        "market_symbols_count": int,
        "reasoning_logs_count": int
    }
}
```

## Graph Flow (termination)
```
portfolio_execute → audit → END
                   ↗           ↑
risk_guard (VETOED) ───────────┘
```

## Rules / Constraints
- `portfolio_execute` always checks `is_vetoed` before proceeding (defensive)
- Node names: `desk_portfolio_execute` and `audit` in the LangGraph
- Audit is terminal — no further state mutations
- Paper mode updates account snapshot after each execution for next run's context
