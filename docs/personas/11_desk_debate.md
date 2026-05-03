# Node: Desk Debate (Synthesis — Investment Committee / 投資委員會辯論)

> **This is a LangGraph node function, not a standalone agent class.**

## Position
Synthesis layer — the investment committee meeting. Appends to `debate_transcript`.

## Goals
- Fuse all Tier-0 alpha desk outputs + risk snapshot into a single human-readable memo.
- The transcript is consumed by Signal Arbitrator (deterministic or LLM).

## SOP
1. **Input**: State with all Tier-0 desk outputs + risk snapshot.
2. **Process**: Construct structured debate transcript rows from each desk's verdict.
3. **Output**: Appends rows to `state.debate_transcript`.
4. **Feedback**: None — stateless per-cycle.

## Rules / Constraints
- Deterministic (no LLM) — purely structural aggregation.
- Output is one of many inputs to Signal Arbitrator.
