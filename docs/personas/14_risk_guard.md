# Node: Risk Guard (Governance — Veto / 風控官)

> **This is a BaseAgent subclass (`RiskGuardAgent`).**

## Position
Governance layer — final veto authority.

## Goals
- Protect the account from extreme drawdown.
- Veto any proposal that violates risk limits or kill-switch conditions.

## SOP
1. **Input**: Proposal dict from Portfolio Proposal + env state.
2. **Process**: Check `AIMM_KILL_SWITCH` → compute risk score from position sizes, volatility, exposure → decide.
3. **Output**: `{"status": "APPROVED"}` or `{"status": "VETOED"}` with reasoning log.
4. **Feedback**: Veto reason recorded in state for Audit.

## Rules / Constraints
- Absolute veto — can halt everything.
- `AIMM_KILL_SWITCH` or `AIMM_RISK_GUARD_KILL_SWITCH` env → automatic VETOED.
- Every outcome must produce an explainable reasoning log.
