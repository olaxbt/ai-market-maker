# Persona: Portfolio Proposal (投资组合提议)

## Position
Portfolio management node that translates the arbitrator's signal decision into a concrete portfolio proposal with sizing, allocation suggestions, and trade parameters. Uses the `PortfolioManagementAgent` with optional LLM proposal when `llm_mode_enabled()`.

## Agent Classification
- **Agent ID**: N/A (Portfolio)
- **Type**: Portfolio / Sizing
- **Code Class**: `PortfolioManagementAgent` (`src/agents/portfolio_management.py`) + `portfolio_proposal` node function
- **Enabled by default**: Yes

## Goals
- Convert `trade_intent` + `proposed_signal` into a concrete position proposal with sizing
- Incorporate risk metrics, quant analysis, and valuation context into sizing decisions
- Fall back cleanly from LLM to deterministic agent if LLM proposal fails

## SOP
1. **Input**: `ticker`, `market_data`, `pattern_analysis`, `sentiment_analysis`, `arb_analysis`, `quant_analysis`, `valuation`, `risk`, `liquidity`, `proposed_signal` (strategy context), `trade_intent`, `run_mode`, `shared_memory`
2. **Process**:
   - If `llm_mode_enabled()`: call `llm_portfolio_proposal(state)` for LLM-generated proposal
   - If LLM fails or `llm_mode` disabled: call `PortfolioManagementAgent.analyze()` with all context inputs
   - Merge `strategy_context` from `proposed_signal` into the proposal
3. **Output**:
   - `proposal` — the portfolio proposal dict (trades, sizing, allocation)
   - `proposed_signal` — updated with proposal params and upstream signal meta
4. **Telemetry**: FlowEvent reasoning entry with proposal summary

## Data Contract
```python
{
    "proposal": {
        "status": "success" | "error",
        "trades": [          # list of trade suggestions
            {
                "symbol": str,
                "side": "buy" | "sell",
                "qty": float,
                "price": float | None,
                "confidence": float,
                "reason": str
            }
        ],
        "strategy_context": { ... },  # from proposed_signal
        # ... additional portfolio fields
    },
    "proposed_signal": {
        "action": "PROPOSAL",
        "params": proposal_dict,  # from PortfolioManagementAgent
        "meta": {
            "source": "portfolio_proposal",
            "upstream_signal": state.proposed_signal
        }
    }
}
```

## Rules / Constraints
- Receives `trade_intent` from the arbitrator — portfolio proposal is secondary sizing, not a new decision
- Falls back from LLM to deterministic agent on any failure
- Backtest mode: reads external cash/positions from `shared_memory.backtest` for position-aware math
- Upstream signal context preserved in `proposed_signal.meta.upstream_signal`
