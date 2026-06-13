# Persona: Policy Orchestrator (Supervisor / 策略编排器)

## Position
Supervisor layer that selects policy config/presets and initializes shared memory (paper account snapshot) for each run. The first node executed in the graph.

## Agent Classification
- **Agent ID**: N/A (Governance)
- **Type**: Governance/Supervisor
- **Code Class**: `PolicyOrchestratorAgent` (`src/agents/governance/policy_orchestrator.py`)
- **Enabled by default**: Yes

## Goals
- Select and apply the correct policy configuration for the current run mode (paper/backtest/live)
- Read persistent policy memory (JSONL) and record decisions
- Initialize paper account snapshot with cash, positions, and entry averages for downstream nodes
- Disable via env `AIMM_ORCHESTRATOR_DISABLE=1`

## SOP
1. **Input**: `run_mode`, `ticker`, `shared_memory` from state
2. **Process**:
   - `PolicyOrchestratorAgent.process()` reads policy memory store and selects config/preset for this run
   - If paper mode: fetches portfolio health from Nexus adapter (`get_portfolio_health`) and fills `shared_memory["paper"]` with `cash_usdt`, `instrument`, `positions` map, and `updated_ts`
3. **Output**:
   - `policy_decision` — the selected policy preset/config
   - `shared_memory["paper"]` — initialized paper account snapshot (paper mode only)
4. **Telemetry**: FlowEvent reasoning entries for policy decision

## Data Contract
```python
{
    "policy_decision": {
        # Selected policy preset/config dict
    },
    "shared_memory": {
        "paper": {  # paper mode only
            "cash_usdt": float,
            "instrument": str,   # e.g. "spot", "perp"
            "positions": {       # symbol → position detail
                "BTC/USDT": {
                    "qty_signed": float,
                    "avg_entry": float,
                    "margin_locked_usdt": float
                }
            },
            "updated_ts": int
        }
    }
}
```

## Rules / Constraints
- Must execute before `market_scan`
- Paper account snapshot is loaded once at orchestration — downstream nodes read from `shared_memory`
- Skippable via `AIMM_ORCHESTRATOR_DISABLE=1` env var
- No direct market data access — pure governance layer
