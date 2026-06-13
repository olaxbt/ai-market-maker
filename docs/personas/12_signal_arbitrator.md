# Persona: Signal Arbitrator — Weighted Convergence (信号仲裁 / 加权收敛仲裁器)

## Position
Core arbitration node that synthesizes all 9 Tier-0 agents' signals into a single trade decision using deterministic weighted convergence. Replaces the legacy LLM arbitrator as the default mode. Produces the `trade_intent` that drives portfolio sizing.

## Agent Classification
- **Agent ID**: N/A (Arbitration)
- **Type**: Arbitration / Signal Synthesis
- **Code Class**: `weighted_arbitrator_node` (`src/workflow/weighted_arbitrator.py`) + `compute_weighted_arbitration()` (`src/workflow/weight_assigner.py`)
- **Enabled by default**: Yes (weighted_convergence mode)
- **Alternative**: `AIMM_ARBITRATOR_MODE=llm` for LLM-based arbitrator

## Goals
- Compute per-agent weighted composites from standardized Tier-0 contracts
- Compute global weighted composite score with confidence and consensus metrics
- Apply threshold gating (BUY/SELL/HOLD) with alignment protection
- Derive `trade_intent` contract for the execution engine
- Build synthesis board evidence for trace UI

## SOP
1. **Input**: `tier0_contracts` (list of contract dicts), `ticker`, `run_mode`, `shared_memory`
2. **Process**:

   **Phase 1 — Weight Assigner** (`weight_assigner.compute_weighted_arbitration()`):
   1. Group contracts by agent ID → `tier0_contracts_by_agent()`
   2. For each enabled agent, extract factor signals via per-agent extractor (`_agent_*_factors`)
   3. Normalize each factor to [0, 1] (1.0 = max bullish)
   4. Compute agent composite = Σ(factor_weight × factor_normalized)
   5. Weight by `AGENT_WEIGHTS_DEFAULT`

   **Phase 2 — Global Score** (`compute_global_weighted_score()`):
   - composite = Σ(agent_weight × agent_composite) / total_weight
   - confidence = |composite_magnitude| × min(1.0, 0.5 + consensus_ratio × 0.5)

   **Phase 3 — Decision Gating**:
   - BUY: composite ≥ 0.60 AND confidence ≥ 0.50
   - SELL: composite ≤ 0.40 AND confidence ≥ 0.50
   - HOLD: else

   **Phase 4 — Alignment Gating**:
   - If directional (BUY/SELL) and active factors < 3 → revert to HOLD

   **Phase 5 — Execution Intent** (`derive_trade_intent()`):
   - Map stance + confidence → BUY/SELL/HOLD action
   - Compute max_notional_usd from cash + leverage + policy settings

   **Phase 6 — Synthesis Board** (`build_synthesis_board()`):
   - Build bull/bear evidence lines with consensus snapshot for UI

3. **Output**:
   - `proposed_signal` — standardized proposal shape (same as LLM path)
   - `trade_intent` — execution contract with action, confidence, constraints, cash context
   - `reasoning_logs` — per-agent factor breakdown + final decision
   - `arbitration_result` — compact summary (composite, confidence, stance, conviction, alignment)

## Default Weights
```python
AGENT_WEIGHTS_DEFAULT = {
    "1.1": 0.05,  "1.2": 0.05,
    "2.1": 0.25,  "2.2": 0.10,  "2.3": 0.30,
    "3.1": 0.05,  "3.2": 0.05,
    "4.1": 0.05,  "4.2": 0.15,  # 4.1 disabled by default
}
```

## Decision Thresholds (v4 Config)
```python
BUY:  min_composite=0.60, min_confidence=0.50
SELL: max_composite=0.40, min_confidence=0.50
alignment_gating: min_factors_for_directional=3
```

## Data Contract
```python
# proposed_signal
{
    "action": "PROPOSAL",
    "params": {
        "stance": "bullish" | "bearish" | "neutral",
        "confidence": float,
        "reasons": [str, ...],
        "tool_events": [],
        "debate_entries": int,
        "weighted_arbitrator": True,
        "composite_score": float,
        "conviction_level": "none" | "low" | "medium" | "high",
        "consensus_ratio": float,
        "alignment_gated": bool,
        "agent_signals": [{agent_summary}, ...]
    },
    "meta": {
        "source": "weighted_arbitrator",
        "mode": "weighted_convergence"
    }
}

# trade_intent
{
    "ticker": str,
    "action": "BUY" | "SELL" | "HOLD",
    "confidence": float,
    "reasons": [str, ...],
    "constraints": {
        "max_notional_usd": float | None,
        "requires_price": True
    },
    "context": {
        "run_mode": str,
        "cash_usd": float | None,
        "qty_base": float | None,
        "price": float | None
    },
    "meta": {
        "source": "execution_intent_v1",
        "derived_from": "proposed_signal.params.stance",
        "min_confidence_directional": 0.45
    }
}
```

## Rules / Constraints
- Disabled agents (weight = 0 or in `disabled_agents` set) excluded from composite
- Agent 4.1 (Whale) disabled by default
- Alignment gating prevents under-powered directional decisions (< 3 active factors)
- Confidence clamped to [0, 0.95] in execution intent
- HOLD override if bearish + short disallowed + flat book
- Per-agent factor breakdown logged in reasoning entries for full transparency
