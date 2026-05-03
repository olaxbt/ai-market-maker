# Hedge Fund Agent Personas

This directory documents the **14 persona agents** in the OlaXBT multi-agent hedge fund system, plus supporting execution nodes. Each `.md` file corresponds to one runtime node in the LangGraph workflow, with some tier-0 agents merged where code analysis showed overlapping data sources and processing.

## Architecture

```
                    ┌──────────────────────┐
                    │  Policy Orchestrator │  (n0) — config/preset
                    └──────────┬───────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │  Alpha       │    │  Synthesis   │    │  Governance  │
    │  Desks (8)   │    │  Layer       │    │              │
    │ (Tier-0)     │    │              │    │ n9  Risk     │
    │              │    │ n10 Debate   │    │     Desk     │
    │ n1  Scan     │    │ n11 Signal   │    │ n13 Risk     │
    │ n2  Macro    │    │    Arb       │    │     Guard    │
    │ n3  News     │    │ n12 Proposal │    └──────────────┘
    │ n4  Tech TA  │    │              │
    │ n5  OI       │    │ (n14 Exec    │    ┌──────────────┐
    │ n6  Retail   │    │  = broker)   │    │  Log Node    │
    │ n7  Pro Bias │    └──────────────┘    │ n15 Audit    │
    │ n8  Microstr │         │              └──────────────┘
    └──────────────┘         │
         │                   │
         ▼                   ▼
    ┌────────────────────────────────────────────┐
    │    Parallel alpha → Risk → Debate →        │
    │    Signal → Proposal → Risk Guard → Exec   │
    └────────────────────────────────────────────┘
```

## 14 Decision Agents + Supporting Nodes

| # | File | Node | Actor | Type | Role |
|---|------|------|-------|------|------|
| **1** | `01_policy_orchestrator.md` | n0 | policy_orchestrator | Agent class | Config/preset selector |
| **2** | `02_market_scan.md` | n1 | market_scan | Agent class | CCXT + CoinGecko fetch |
| **3** | `03_monetary_sentinel.md` | n2 | monetary_sentinel | Module fn | Macro economist |
| **4** | `04_news_narrative_miner.md` | n3 | news_narrative_miner | Module fn | Event-driven analyst |
| **5** | `05_technical_analysis_desk.md` | n4+n6 | (merged) | Mixed | Chart patterns + TA-Lib |
| **6** | `06_open_interest_positioning.md` | n5 | statistical_alpha | Module fn | OI / positioning |
| **7** | `07_retail_hype_tracker.md` | n7 | retail_hype_tracker | Agent class | Behavioural psychologist |
| **8** | `08_pro_bias_analyst.md` | n8 | pro_bias_analyst | Agent class | Smart-money flow |
| **9** | `09_market_microstructure.md` | n9+n10 | (merged) | Mixed | On-chain + order book |
| **10** | `10_risk_desk.md` | n11 | risk | Agent class | Risk context snapshot |
| **11** | `11_desk_debate.md` | n12 | desk_debate | Node function | IC memo synthesis |
| **12** | `12_signal_arbitrator.md` | n13 | signal_arbitrator | Node function | Final stance |
| **13** | `13_portfolio_proposal.md` | n14 | portfolio_proposal | Node function | Capital allocation |
| **14** | `14_risk_guard.md` | n15 | risk_guard | Agent class | Veto authority |

## Non-Agent Supporting Nodes

| # | File | Node | Actor | Type | Role |
|---|------|------|-------|------|------|
| — | `15_portfolio_execute.md` | n16 | portfolio_execute | Node function | CCXT order routing |
| — | (in README) | n17 | audit | Log function | Event persistence |

## Merges Applied

| Original Nodes | Merged Into | Rationale |
|----------------|-------------|-----------|
| n4 Pattern Recognition + n6 Technical TA | `05_technical_analysis_desk.md` | 80% input overlap (OHLCV), same analytical question |
| n9 Whale Behavior + n10 Liquidity Flow | `09_market_microstructure.md` | 60% input overlap (per_symbol data), same market health question |

## Node Types

- **Agent class**: A `BaseAgent` subclass with its own `.py` file in `src/agents/`.
- **Module fn**: A stateless function defined in a module under `src/agents/`.
- **Node function**: A stateless function defined in `src/main.py` that operates on the graph state.
