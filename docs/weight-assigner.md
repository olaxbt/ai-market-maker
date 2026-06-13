# Weight Assigner — Design & Behaviour

## Purpose

Maps raw Tier-0 perception agent outputs into a single **weighted composite score**
using the v4 config factor-weight matrix. It is the "quantitative spine" of the
arbitration pipeline — no LLM calls, deterministic math only.

## Architecture

```
Tier-0 Contracts (9 agents)
        │
        ▼
┌─────────────────────────────────────────────┐
│          Weight Assigner                     │
│                                              │
│  1. Per-Agent Factor Extraction              │
│     ┌─────────────────────────────────────┐  │
│     │ 9 extractors mapped by agent_id     │  │
│     │ Each reads contract fields          │  │
│     │ Returns dict[factor_id → signal]    │  │
│     └─────────────────────────────────────┘  │
│                                              │
│  2. Factor Normalization                     │
│     ┌─────────────────────────────────────┐  │
│     │ Raw → [0, 1] bullish direction      │  │
│     │ 1.0 = max bullish conviction        │  │
│     │ 0.0 = max bearish conviction        │  │
│     │ 0.5 = neutral                       │  │
│     └─────────────────────────────────────┘  │
│                                              │
│  3. Weighted Composite                       │
│     ┌─────────────────────────────────────┐  │
│     │ agent_composite = Σ(w_f × signal_f) │  │
│     │ global_composite = Σ(w_a × comp_a)  │  │
│     └─────────────────────────────────────┘  │
│                                              │
│  4. Confidence Formula                       │
│     ┌─────────────────────────────────────┐  │
│     │ confidence = |mag| × min(1.0,       │  │
│     │   0.5 + consensus_ratio × 0.5)      │  │
│     └─────────────────────────────────────┘  │
│                                              │
└─────────────────────────────────────────────┘
        │
        ▼
  ArbitrationResult
```

## Core Formulas

### Agent Composite

```
composite_a = Σ(factor_weight × signal_normalized)
```

Each agent has a defined factor set from the v4 config:

| Agent     | Factors                                                    |
|-----------|------------------------------------------------------------|
| 1.1 Macro | macro_bias (regime 60% + liquidity 40%)                    |
| 1.2 News  | sentiment 0.28, impact 0.38, event_type 0.19, freshness 0.15 |
| 2.1 Pattern| setup 0.40, quality 0.30, timeframe 0.20, volume 0.10    |
| 2.2 Stats | alpha_signal 0.50, z_score 0.25, regime 0.25              |
| 2.3 TA    | rsi 0.15, macd 0.20, obv 0.10, atr 0.05, adx 0.15,       |
|           | ema_cross 0.10, volume 0.15, pattern_rec 0.10              |
| 3.1 Retail| fomo 0.35, social_volume 0.25, divergence 0.40             |
| 3.2 SmartM| etf 0.40, funding_rate 0.30, oi_delta 0.30                |
| 4.1 Whale | dump 0.50, concentration 0.25, wallet_flow 0.25            |
|           | *(disabled by default)*                                    |
| 4.2 LiqOF | slippage 0.35, imbalance 0.35, depth_skew 0.30            |

### Global Composite

```
global_composite = Σ(agent_weight × composite_a) / Σ(enabled_agent_weights)
```

Agent weights from v4 config:

| ID   | Weight | Agent Area          |
|------|--------|---------------------|
| 1.1  | 0.05   | Macro               |
| 1.2  | 0.05   | News/Narrative      |
| 2.1  | 0.25   | Pattern Recognition |
| 2.2  | 0.10   | Statistical         |
| 2.3  | 0.30   | Technical TA        |
| 3.1  | 0.05   | Retail Sentiment    |
| 3.2  | 0.05   | Smart Money         |
| 4.2  | 0.15   | Liquidity/Flow      |

**Key insight:** Technical (2.3) + Pattern (2.1) + Liquidity (4.2) = 70% of the vote.
Macro + News + Sentiment + Smart Money = 20%.
This reflects a **price-action-first** philosophy.

### Confidence

```
magnitude        = |composite − 0.5| × 2.0        # [0, 1]
consensus_ratio  = max(bullish_count, bearish_count) / total_enabled
confidence       = magnitude × min(1.0, 0.5 + consensus_ratio × 0.5)
```

- **High confidence** (≥0.75): strong conviction, most agents agree
- **Medium confidence** (≥0.55): directional bias but some disagreement
- **Low confidence** (>0.0): weak signal
- **None** (0.0): flat neutral, no conviction

## Factor Extraction Behaviour

### Normalization Strategy

Each factor extractor interprets its agent's Tier-0 contract fields and maps them
to `[0, 1]` where **1.0 is maximum bullish conviction**:

| Raw Signal          | Bullish → 1.0 | Bearish → 0.0 |
|---------------------|---------------|---------------|
| RSI                 | 30 (oversold) | 70 (overbought)|
| FOMO Level          | 0 (fear)      | 100 (euphoria) |
| Setup Score         | 100           | 0              |
| Z-Score             | +3.0          | −3.0           |
| Slippage Risk       | 0 (tight)     | 100 (wide)     |
| Macro Regime        | Risk-On       | Risk-Off       |

Inverted signals (RSI, FOMO, Slippage) are explicitly `_invert()`-ed so the scale
is **always bullish-direction**: you don't need to remember which raw values are
"good" or "bad" — 1.0 always means "supports a long position."

### Missing Data Handling

When Tier-0 contracts are absent or fields are null:

1. **Explicit defaults** — each extractor has hardcoded neutral (0.50) fallbacks
2. **Proxy derivation** — missing fields are approximated from available ones
   (e.g., social_volume derived from FOMO_Lewel)
3. **No hallucination** — the engine never fabricates data; it explicitly tags
   proxy fields in the `FactorSignal.source_field`

## State Dependency

The weight assigner reads **only** from these HedgeFundState keys:

```
tier0_contracts            → tier0_contracts_by_agent() index
(no other state accessed)
```

This means it is **stateless**: given the same Tier-0 contracts, it always
produces the same result. This is critical for:
- **Deterministic backtesting** — identical contracts = identical scores
- **Audit trail** — scores can be re-computed from stored contracts
- **Testing** — no mocking needed beyond contract fixtures

## Opt-In / Opt-Out

| Mechanism              | Effect                                              |
|------------------------|-----------------------------------------------------|
| `disabled_agents` set  | Skips agent entirely (weight=0, no factors computed)|
| Agent `enabled=false`  | Tier-0 contract still built, but excluded from score |
| Weight overrides       | Runtime replacement of default weight map           |
| Arbitrator mode switch | `weighted_convergence` → uses this engine           |

## Edge Cases

| Case                             | Behaviour                                                  |
|----------------------------------|------------------------------------------------------------|
| No Tier-0 contracts              | All agents return composite=0.5, global=0.5, confidence=0  |
| Single agent enabled             | Global composite = that agent's composite                  |
| All factors at boundary (0 or 1) | Agent composite clamped to [0,1], triggers max conviction  |
| Disabled agents (e.g., whale 4.1)| Weight redistributed among remaining enabled agents        |
| Weight sum ≠ 1.0                 | Normalized by total enabled weight, not rejected           |
