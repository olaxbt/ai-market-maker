# Persona: Risk Guard (风险警卫 / 治理层否决权)

## Position
Governance node with veto power. Acts as the final check before execution — evaluates the portfolio proposal against risk policy and can VETO the entire run. Implements the kill switch mechanism.

## Agent Classification
- **Agent ID**: N/A (Governance)
- **Type**: Governance / Risk Officer
- **Code Class**: `RiskGuardAgent` (`src/agents/governance/risk_guard.py`)
- **Enabled by default**: Yes

## Goals
- Evaluate the portfolio proposal against risk policy rules (position limits, drawdown, concentration)
- Return APPROVED or VETOED with reasoning and risk score
- Expose kill switch via env vars (`AIMM_KILL_SWITCH`, `AIMM_RISK_GUARD_KILL_SWITCH`)
- Route execution skip on veto (graph routes to audit instead of portfolio_execute)

## SOP
1. **Input**: `proposal`, `shared_memory`, `ticker`, `run_mode` from state
2. **Process**:
   - `RiskGuardAgent.process()` checks the proposal against risk policy (`FundPolicy`)
   - Active kill switch → immediate VETO with explanation
   - Position limit checks, drawdown thresholds, concentration risk
   - Returns `status` (APPROVED/VETOED), `risk_score` (float), `reasoning` (dict with `thought`)
3. **Output**:
   - `risk_guard` — full decision dict
   - `risk_report` — same as decision for downstream audit
   - `is_vetoed` — boolean flag
   - `veto_reason` — explanation string if vetoed
   - If vetoed: `execution_result` with `status = "skipped"`
4. **Telemetry**: `FlowEvent.risk_guard` with status, risk score, and reasoning; published to `LogPublisher` with `veto_status`

## Data Contract
```python
# On APPROVE:
{
    "status": "APPROVED",
    "risk_score": float,
    "reasoning": {"thought": str, ...}
}

# On VETO:
{
    "status": "VETOED",
    "risk_score": float,  # typically high
    "reasoning": {"thought": str, ...}
}
```

State flags set by this node:
```python
{
    "risk_guard": { ... },         # full decision
    "risk_report": { ... },        # same as risk_guard
    "is_vetoed": True | False,
    "veto_reason": str,
    "execution_result": {          # only when vetoed
        "status": "skipped",
        "message": "Execution vetoed by Risk Guard",
        "risk_guard": { ... }
    }
}
```

## Rules / Constraints
- Graph routing: VETOED → `audit` (skip portfolio_execute); APPROVED → `portfolio_execute`
- Kill switch env vars: `AIMM_KILL_SWITCH=1` or `AIMM_RISK_GUARD_KILL_SWITCH=1` force immediate veto
- Decision is final — portfolio_execute checks `is_vetoed` and skips if set
- Respects `FundPolicy` limits (position concentration, max notional, short-allowed flag)
