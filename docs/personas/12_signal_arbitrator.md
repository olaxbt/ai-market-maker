# Node: Signal Arbitrator (Decision — Final Stance / 信號仲裁者)

> **This is a LangGraph node function, not a standalone agent class.**
> Optional LLM variant via `signal_arbitrator_llm` when `AIMM_USE_LLM_ARBITRATOR` is set.

## Position
Decision layer — the final cross-desk arbitrator (Tier-2 synthesis).

## Goals
- Compute final bullish/bearish stance from desk outputs, debate transcript, and risk context.
- Default to NEUTRAL unless evidence is strong.

## SOP
1. **Input**: State with all Tier-0 scores + debate transcript + risk snapshot.
2. **Process**: `compute_legacy_arbitrator_scores()` → momentum score + consensus check → determine stance.
3. **Output**: Dict with `stance` (bullish/bearish/neutral), confidence, bull/bear score, high-vol flags.
4. **Feedback**: None — stateless per-cycle.

## Rules / Constraints
- Two variant modes: deterministic math (`signal_arbitrator`) or LLM-driven (`signal_arbitrator_llm`).
- Weighted evidence: Tier-0 consensus counts alongside individual desk scores.
- Never exceeds confidence > 0.95 (LLM variant enforced via prompt).
