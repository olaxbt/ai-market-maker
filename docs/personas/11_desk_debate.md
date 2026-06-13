# Persona: Desk Debate (辩论台 / Tier-2 综合)

## Position
Pre-arbitration debate stage that generates two-sided evidence lines from Tier-0 contracts. Always produces deterministic bull/bear summaries. Optionally adds LLM desk turns (Desk_Risk with depth tool access, Desk_Tape narrative-only) when `AIMM_LLM_DESK_DEBATE=1`.

## Agent Classification
- **Agent ID**: N/A (Tier-2 Synthesis)
- **Type**: Debate / Evidence Synthesis
- **Code Class**: `desk_debate` node function (`src/workflow/desk_debate.py`)
- **Enabled by default**: Yes (deterministic always; LLM optional)

## Goals
- Produce structured bull/bear evidence lines from Tier-0 contract fields
- Compute a deterministic legacy stance preview as reference
- Provide the downstream arbitrator (weighted or LLM) with grounded evidence context
- Optionally host LLM desk debate turns for narrative reasoning

## SOP
1. **Input**: `ticker`, `tier0_contracts`, `risk`, `universe`, `debate_transcript` from state
2. **Process**:
   - **Deterministic** (always): `bull_evidence_lines()` + `bear_evidence_lines()` from `tier2_context.py`
     - Scans each agent's contract fields for constructive (bull) and defensive (bear) signals
     - Calls `legacy_deterministic_stance_preview()` for score reference
   - **LLM** (optional, `AIMM_LLM_DESK_DEBATE=1`):
     - Desk_Risk: LLM with optional `nexus.fetch_market_depth` tool
     - Desk_Tape: LLM with no tools (narrative-only)
     - Both desks use structured format: Decision / Evidence / Risks / Would change mind if
3. **Output**:
   - `debate_transcript` — list of entries appended to state (deterministic + optional LLM)
   - `reasoning_logs` — debate summary with entry count
4. **Telemetry**: FlowEvent reasoning entry with debate preview (truncated to 320 chars)

## Evidence Lines (Deterministic)
| Agent | Bull Evidence | Bear Evidence |
|-------|-------------|---------------|
| 1.1 Macro | Risk-on regime (state=2) | Risk-off regime (state=0) |
| 1.2 News | Low impact (<40) | High impact (≥55) or Black Swan |
| 2.1 Pattern | Setup ≥ 55 | Setup < 45 |
| 2.2 Alpha | Strong Buy signal | Strong Sell signal |
| 2.3 TA | RSI oversold, MACD+ | RSI stretched, MACD- |
| 3.1 Hype | FOMO < 75, no divergence | FOMO ≥ 80 + divergence |
| 3.2 Smart | ETF Accumulation | ETF Distribution |
| 4.1 Whale | Dump prob < 0.45 | Dump prob ≥ 0.45 |
| 4.2 Liquidity | Slippage < 75 | Slippage ≥ 75 |

## Data Contract
```python
{
    "debate_transcript": [
        {
            "speaker": "desk_risk" | "desk_tape" | "llm_desk_risk" | "llm_desk_tape",
            "role": "macro_and_guardrails" | "technical_and_flow" | "llm_tools_depth" | "llm_narrative_only",
            "text": str,           # structured memo
            "tools_available": [str, ...],     # LLM desk only
            "tools_used": [str, ...],          # LLM desk only
            "tool_events_count": int           # LLM desk only
        },
        ...
    ]
}
```

## Rules / Constraints
- Deterministic debate is always active — no API cost
- LLM debate requires `AIMM_LLM_DESK_DEBATE=1` env var AND `AIMM_ARBITRATOR_MODE=llm`
- Full transcript stored in state; preview (320 chars) used for reasoning logs
- Full transcript can be included in flow events via `AIMM_FLOW_INCLUDE_FULL_DEBATE=1`
- Desk_Risk (LLM) may call tools up to 2 rounds; Desk_Tape has no tools
- Prompt settings configurable via `agent_prompts` config `desk_debate` actor settings
