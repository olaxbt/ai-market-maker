# Weighted Convergence Arbitrator — Design & Behaviour

## Purpose

The arbitrator is the **decision gate** of the AIMM pipeline. It takes the
weighted composite scores from the weight assigner, applies configurable
thresholds, and produces an executable `trade_intent`.

## Pipeline Position

```
Tier-0 Agents → desk_risk → desk_debate
    → Weight Assigner (scores)
    → Weighted Arbitrator (decision gate)
    → portfolio_proposal → desk_risk_guard → portfolio_execute → audit
```

The arbitrator replaces the `signal_arbitrator` node. It is a **deterministic
formula engine** — no LLM costs, no API latency, fully reproducible.

## Decision Flow

```
                    ┌─────────────┐
                    │ Composite   │
                    │ Score [0,1] │
                    └──────┬──────┘
                           │
                           ▼
                 ┌─────────────────────┐
                 │    Stance Switch    │
                 │                     │
                 │ ≥ 0.55 → bullish    │
                 │ ≤ 0.45 → bearish    │
                 │ else   → neutral    │
                 └─────────┬───────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │   Decision Thresholds    │
              │                          │
              │ BUY:  composite ≥ 0.60   │
              │       AND conf ≥ 0.50    │
              │                          │
              │ SELL: composite ≤ 0.40   │
              │       AND conf ≥ 0.50    │
              │                          │
              │ HOLD: everything else    │
              └──────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │    Alignment Gating      │
              │                          │
              │ If directional:          │
              │   active_factors ≥ 3 ?   │
              │   YES → let pass         │
              │   NO  → override→HOLD    │
              └──────────────────────────┘
                           │
                           ▼
              ┌──────────────────────────┐
              │     Trade Intent         │
              │  (BUY / SELL / HOLD)     │
              │  + confidence + reasons  │
              └──────────────────────────┘
```

## Threshold Configuration

From the v4 config:

```json
{
  "decision_threshold": {
    "buy":  { "min_composite": 60, "min_confidence": 50 },
    "sell": { "max_composite": 40, "min_confidence": 50 },
    "hold": { "else": true }
  },
  "alignment_gating": {
    "enabled": true,
    "min_factors_for_directional": 3,
    "risk_override_if_blocked": true
  }
}
```

## Behaviour Matrix

| Composite | Confidence | Consensus  | Stance    | Decision | Conviction |
|-----------|------------|------------|-----------|----------|------------|
| 0.72      | 0.82       | 6/8 bull   | bullish   | BUY      | high       |
| 0.65      | 0.58       | 5/8 bull   | bullish   | BUY      | medium     |
| 0.62      | 0.45       | 4/8 bull   | bullish   | HOLD     | low        |
| 0.53      | 0.12       | 3/8 bull   | neutral   | HOLD     | none       |
| 0.38      | 0.68       | 5/8 bear   | bearish   | SELL     | medium     |
| 0.35      | 0.55       | 4/8 bear   | bearish   | HOLD     | low        |
| 0.28      | 0.88       | 7/8 bear   | bearish   | SELL     | high       |

**Key observations:**

- **Composite must be directional AND confidence must clear threshold.**
  High confidence with neutral composite → HOLD (correct — no clear direction).
  Directional composite with low confidence → HOLD (conservative — disagreement).
- **Alignment gating** blocks any BUY/SELL when fewer than 3 total factors
  contributed to the score. Prevents decisions on thin data.
- **Disabled agents** (e.g., whale 4.1) don't contribute to consensus ratio.

## Output Shape

The arbitrator produces a `proposed_signal` with the same contract shape as the
LLM arbitrator, making it a **drop-in replacement**:

```python
{
    "action": "PROPOSAL",
    "params": {
        "stance": "bullish",
        "confidence": 0.74,
        "reasons": ["BUY signal: composite=0.6727 >= 0.60, confidence=0.74 >= 0.50", ...],
        "tool_events": [],
        "debate_entries": 0,
        "weighted_arbitrator": True,
        "composite_score": 0.6727,
        "conviction_level": "medium",
        "consensus_ratio": 0.625,
        "alignment_gated": False,
        "agent_signals": [...]          # per-agent breakdown
    },
    "meta": {
        "source": "weighted_arbitrator",
        "mode": "weighted_convergence"
    }
}
```

## Reasoning Logs

Each arbitrator run produces **one log entry per enabled agent** plus the global
decision. Per-agent entries contain the full factor breakdown:

```json
{
    "node": "signal_arbitrator",
    "decision": {
        "agent_id": "2.3",
        "agent_type": "technical_ta",
        "label": "Technical Analysis",
        "composite": 0.7214,
        "agent_weight": 0.30,
        "weighted_composite": 0.2164,
        "stance": "bullish",
        "confidence": 0.943,
        "factor_count": 8,
        "factor_breakdown": {
            "rsi": { "raw": 35.0, "normalized": 0.65, "weight": 0.15 },
            "macd": { "raw": 15.0, "normalized": 0.85, "weight": 0.20 }
        }
    }
}
```

## Opt-In / Opt-Out

The arbitrator supports three modes via `AIMM_ARBITRATOR_MODE`:

| Mode                   | Engine                   | Use Case                     |
|------------------------|--------------------------|------------------------------|
| `weighted_convergence` | `weighted_arbitrator.py` | Default — deterministic      |
| `llm`                  | `signal_arbitrator_llm`  | LLM-based synthesis          |


Additionally, disable the arbitrator entirely by setting `AIMM_ARBITRATOR_DISABLE=1`
(not yet implemented — future: routes from desk_debate directly to portfolio_proposal
with neutral stance).

## Portability for Agentic Trading

The arbitrator is designed as a **standalone module** with zero internal
dependencies on HedgeFundState:

| Component                  | Dependencies                              | Size  |
|----------------------------|--------------------------------------------|-------|
| `schemas/arbitration.py`   | None (pure dataclasses)                    | 161 lines |
| `workflow/weight_assigner.py` | schemas.arbitration + tier0_contract  | 560 lines |
| `workflow/weighted_arbitrator.py` | + execution_intent, tier2_context | 263 lines |

To extract for agentic trading:

1. Copy `schemas/arbitration.py` — no changes needed
2. Copy `workflow/weight_assigner.py` — dependency on `tier0_contract_by_agent()`
3. Provide a `Tier0ContractReader` interface instead of tight coupling

## Edge Cases

| Scenario                        | Behaviour                                              |
|---------------------------------|--------------------------------------------------------|
| Zero enabled agents             | Returns HOLD with composite=0.5, confidence=0.0        |
| All agents neutral              | HOLD — no threshold cleared                            |
| Perfect consensus (8/8 bullish) | Confidence capped at magnitude × 1.0                   |
| Alignment gate blocks BUY       | Overridden to HOLD, logged with alignment_reason       |
| Agent weight = 0.00             | Contributing agent skipped (not counted in consensus)  |
