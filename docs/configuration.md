# Configuration & Environment

## Philosophy

AIMM is designed to run **with an LLM token** — no LLM-less fallback paths.
This eliminates the `AI_MARKET_MAKER_USE_LLM` toggle. If you have an
`OPENAI_API_KEY` (or compatible endpoint), the system runs at full capability.

Three configuration layers:

```
.env                        → env vars (secrets, overrides)
config/app.default.json     → app defaults (tuning params, presets)
config/policy.default.json  → trading policy (risk, sizing, rules)
```

---

## Required Environment Variables

| Variable            | Purpose                                       |
|---------------------|-----------------------------------------------|
| `OPENAI_API_KEY`    | LLM provider key (OpenAI / compatible)        |
| `BINANCE_API_KEY`   | Binance API key for market data               |
| `BINANCE_API_SECRET`| Binance API secret                            |
| `NEXUS_API_KEY`     | Olaxbt Nexus data API key                     |

> **No LLM key → the process exits with a clear error.** No fallback, no silent
> degradation. This is intentional — the system is an LLM-native architecture.

---

## Optional Environment Variables

### Arbitrator Mode

| Variable              | Values                                     | Default                |
|-----------------------|--------------------------------------------|------------------------|
| `AIMM_ARBITRATOR_MODE`| `weighted_convergence` / `llm` / `legacy`  | `weighted_convergence` |

- **weighted_convergence** (default): deterministic factor-weighted engine, no LLM cost
- **llm**: LLM-based synthesis (uses OPENAI_API_KEY)
- **legacy**: original Tier-0 consensus voting

### Agent Toggles

| Variable                         | Effect                                  |
|----------------------------------|-----------------------------------------|
| `AIMM_ORCHESTRATOR_DISABLE`      | Skip policy orchestrator node           |
| `AIMM_TA_TIER0_DISABLE`          | Disable technical TA agent              |
| `AIMM_RISK_GUARD_KILL_SWITCH`    | Emergency stop — blocks all trades      |


Each agent derives its enabled/disabled state from:
1. Hardcoded default (e.g., Whale 4.1 is disabled by default)
2. Environment variable override
3. Orchestrator policy override (when orchestrator is active)

### Debug & Observability

| Variable                  | Purpose                                      |
|---------------------------|----------------------------------------------|
| `AIMM_DEBUG_RISK`         | Verbose risk calculation logs                |
| `AIMM_FLOW_INCLUDE_FULL_DEBATE` | Include full debate transcript in output |
| `AIMM_LLM_DESK_DEBATE`    | Enable LLM desk debate (costly)              |
| `STRATEGY_INTERVAL_SEC`   | Graph run interval (default: 180)            |

### Execution

| Variable                          | Values                  | Default |
|-----------------------------------|-------------------------|---------|
| `AI_MARKET_MAKER_ALLOW_LIVE`      | 0 / 1                   | 0       |
| `AI_MARKET_MAKER_EXECUTION_ENGINE`| `legacy` / `oms`        | `legacy`|
| `MODE`                            | `paper` / `live` / `backtest` | `paper` |

---



## Opt-In / Opt-Out Architecture

The system is designed as a **modular pipeline** where each component can be
individually enabled or disabled:

```
policy_orchestrator ── [AIMM_ORCHESTRATOR_DISABLE]
        │
desk_market_scan ── [always on]
        │
├─ monetary_sentinel ── [config weight=0 → skip]
├─ news_narrative_miner ── [config weight=0 → skip]
├─ pattern_recognition_bot ── [config weight=0 → skip]
├─ statistical_alpha_engine ── [config weight=0 → skip]
├─ technical_ta_engine ── [AIMM_TA_TIER0_DISABLE or weight=0]
├─ retail_hype_tracker ── [config weight=0 → skip]
├─ pro_bias_analyst ── [config weight=0 → skip]
├─ whale_behavior_analyst ── [disabled by default in weight config]
├─ liquidity_order_flow ── [config weight=0 → skip]
        │
desk_risk ── [always on]
desk_debate ── [always on, LLM part guarded by AIMM_LLM_DESK_DEBATE]
signal_arbitrator ── [AIMM_ARBITRATOR_MODE selects engine]
portfolio_proposal ── [always on]
desk_risk_guard ── [AIMM_RISK_GUARD_KILL_SWITCH]
portfolio_execute ── [MODE controls real vs paper]
audit ── [always on]
```

### Enabling/disabling agents via weight config

Setting an agent's weight to `0.0` effectively disables it. The remaining enabled
weights are re-normalized automatically:

```python
weights = {"2.1": 0.25, "2.3": 0.30, "4.2": 0.15}  # others set to 0
# Normalized internally: 0.25 + 0.30 + 0.15 = 0.70 ≠ 1.0
# Each weight scaled by 1/0.70: 0.357 + 0.429 + 0.214 = 1.0
```

This is useful for:
- **Minimal mode** (Pattern + TA + Liquidity only → 70% of original voting power)
- **Testing** (single agent active → verify its factor extraction)
- **Abnormal regimes** (disable retail hype during high-vol, etc.)

---

## Layer-Specific Env Design

### Layer 0 — Data Sources (none required, but recommended)
```
BINANCE_API_KEY / SECRET   ← OHLCV data
NEXUS_API_KEY              ← Nexus/Olaxbt data (news, KOL, OI, funding)
ADANOS_API_KEY             ← Optional Adanos crypto sentiment for retail_hype_tracker
TWITTER_BEARER_TOKEN        ← Social sentiment (optional, experimental)
```

### Optional Adanos Market Sentiment

Set `ADANOS_API_KEY` to enrich the Tier-0 `retail_hype_tracker` with Adanos
crypto sentiment for the active universe. The integration calls the Adanos
crypto Reddit sentiment endpoint, maps CCXT pairs such as `BTC/USDT` to `BTC`,
and degrades gracefully if Adanos is unavailable or a token has no data.

| Variable               | Default                                   | Purpose                   |
|------------------------|-------------------------------------------|---------------------------|
| `ADANOS_API_KEY`       | unset                                     | Enables the Adanos feed   |
| `ADANOS_DISABLE`       | `0`                                       | Set to `1` to force off   |
| `ADANOS_API_BASE`      | `https://api.adanos.org/reddit/crypto/v1` | Override API base URL     |
| `ADANOS_TIMEOUT_S`     | `5`                                       | Per-request timeout       |
| `ADANOS_TOTAL_TIMEOUT_S`| `20`                                      | Total feed time budget    |
| `ADANOS_LOOKBACK_DAYS` | `7`                                       | Sentiment window length   |
| `ADANOS_SYMBOL_MAX`    | `8`                                       | Max symbols per graph run |
| `ADANOS_MAX_WORKERS`   | `4`                                       | Concurrent symbol fetches |

### Layer 1 — Agents (optional toggles)
```
AIMM_TA_TIER0_DISABLE      ← Technical TA
```

### Layer 2 — Arbitrator
```
AIMM_ARBITRATOR_MODE       ← Engine selection
```

### Layer 3 — Execution
```
MODE                       ← paper / live / backtest
AI_MARKET_MAKER_ALLOW_LIVE ← double-gate for live
```

### Layer 4 — Safety
```
AIMM_RISK_GUARD_KILL_SWITCH ← emergency stop
```
