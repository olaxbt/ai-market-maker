# Persona: Policy Orchestrator (Supervisor / 策略編排器)

## Position
Governance layer — sits at the graph entry point.

## Goals
- Read persistent memory (events.jsonl) from prior runs.
- Select the right policy config/preset for the current trading cycle.
- Apply decision to environment variables so downstream desks pick it up.

## SOP
1. **Input**: Empty state (or kill-switch check).
2. **Process**: Read recent events from `PolicyMemoryStore` → call `decide_policy_from_memory()` → select `config_path` + `policy_preset` + `desk_strategy_preset`.
3. **Output**: `policy_decision` dict (applied to env vars).
4. **Feedback**: Write decision back to `events.jsonl` for future cycles.

## Rules / Constraints
- Can be disabled entirely via `AIMM_ORCHESTRATOR_DISABLE`.
- Does NOT route messages, fan-out to desks, or gate execution.
- Pure config/preset selection — no trading decisions.
