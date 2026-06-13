# AIMM v4 Personas — Weighted Convergence Architecture

## Architecture Overview

The AI Market Maker (AIMM) v4 replaces the legacy n0-n17 numbering and LLM-centric arbitrator with a **weighted convergence architecture**. Nine tier-0 perception agents (IDs 1.1–4.2) analyze markets in parallel, each producing a standardized Tier-0 JSON contract. A deterministic weight assigner extracts factor signals from these contracts, normalizes them to [0, 1], and computes a global weighted composite score that drives trade decisions.

### Graph Flow

```
policy_orchestrator → market_scan
  → [9 tier-0 agents in parallel]
  → risk → desk_debate → signal_arbitrator
  → portfolio_proposal → risk_guard
  → portfolio_execute → audit
```

### 9 Tier-0 Agents

| ID | Code ID | Name | Role | Weight |
|----|---------|------|------|--------|
| 1.1 | monetary_sentinel | Macro Economist | Macro regime + liquidity score | 0.05 |
| 1.2 | news_narrative_miner | News & Narrative | Event impact + narrative freshness | 0.05 |
| 2.1 | pattern_recognition_bot | Pattern Recognition | Chart geometry + setup quality | 0.25 |
| 2.2 | statistical_alpha_engine | Statistical Alpha | Cross-sectional z-score + alpha signal | 0.10 |
| 2.3 | technical_ta_engine | Technical Analysis | TA-Lib bundle (RSI, MACD, OBV, ATR, ADX, EMA) | 0.30 |
| 3.1 | retail_hype_tracker | Retail Hype | FOMO level + divergence warning | 0.05 |
| 3.2 | pro_bias_analyst | Smart Money | ETF trend + funding rate + OI delta | 0.05 |
| 4.1 | whale_behavior_analyst | Whale Behavior | Dump probability + concentration | 0.05 |
| 4.2 | liquidity_order_flow | Liquidity & Order Flow | Slippage risk + order imbalance + depth skew | 0.15 |

**Disabled by default**: Agent 4.1 (Whale Behavior) — enable by setting weight > 0.

### Persona Files

| File | Persona | Node / Agent |
|------|---------|-------------|
| `01_policy_orchestrator.md` | Policy Orchestrator | Governance: Supervisor |
| `02_market_scan.md` | Market Scan | Data: Market scan & universe selection |
| `03_monetary_sentinel.md` | Agent 1.1 Macro Economist | Tier-0: Macro regime |
| `04_news_narrative_miner.md` | Agent 1.2 News & Narrative | Tier-0: Events & narrative |
| `05_technical_analysis_desk.md` | Technical Analysis Agents | Tier-0: 2.1 Pattern + 2.2 Statistical + 2.3 TA |
| `06_open_interest_positioning.md` | Sentiment & Flow Agents | Tier-0: 3.1 Retail Hype + 3.2 Pro Bias |
| `07_retail_hype_tracker.md` | Agent 3.1 Retail Hype | Tier-0: Behavioral sentiment |
| `08_pro_bias_analyst.md` | Agent 3.2 Smart Money | Tier-0: Institutional flow |
| `09_market_microstructure.md` | Microstructure Agents | Tier-0: 4.1 Whale + 4.2 Liquidity |
| `10_risk_desk.md` | Risk Management | Risk: Position sizing & volatility |
| `11_desk_debate.md` | Desk Debate | Tier-2: Bull/bear evidence lines |
| `12_signal_arbitrator.md` | Signal Arbitrator | Arbitration: Weighted convergence + execution intent |
| `13_portfolio_proposal.md` | Portfolio Proposal | Portfolio: Sizing & allocation |
| `14_risk_guard.md` | Risk Guard | Governance: Veto power |
| `15_portfolio_execute.md` | Portfolio Execute (+ Audit) | Execution: Order placement & audit |

### Decision Thresholds

```python
BUY:  min_composite >= 0.60, min_confidence >= 0.50
SELL: max_composite <= 0.40, min_confidence >= 0.50
HOLD: else
alignment_gating: min_factors_for_directional = 3
```

### Key Changes from v3

| v3 (old) | v4 (new) |
|----------|----------|
| n0–n17 numbered agents | 9 tier-0 agents (1.1–4.2) |
| LLM-centric arbitrator | Weighted convergence arbitrator (default) |
| `AIMM_USE_LLM` toggle | Removed — LLM key required |
| `arbitrator_shadow.py` | Deleted — replaced by weight_assigner |
| Raw signal output | `trade_intent` via `derive_trade_intent()` |
| — | Factor extraction pipeline (`AGENT_FACTOR_MAP`) |
| — | Alignment gating (min 3 factors) |
| — | Opt-in/opt-out via weight=0 in config |
| — | Synthesis board (`tier2_context.py`) |

### Optional LLM Features

- **AIMM_ARBITRATOR_MODE=llm**: Use LLM-based arbitrator instead of weighted convergence
- **AIMM_LLM_DESK_DEBATE=1**: Enable LLM desk debate (Desk_Risk + Desk_Tape LLM turns)
