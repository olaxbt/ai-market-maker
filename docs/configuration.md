# Configuration & Environment

## Philosophy

AIMM is designed to run **with an LLM token** — no LLM-less fallback paths.
This eliminates the `AI_MARKET_MAKER_USE_LLM` toggle. If you have an
`OPENAI_API_KEY` or an OpenAI-compatible provider key, the system runs at full capability.

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
| `AIMM_API_KEY`      | Flow control-plane API key (`x-api-key`)      |
| `AIMM_AUTH_SECRET`  | JWT signing secret for `/auth/*`              |
| `POSTGRES_PASSWORD` | Compose Postgres password                     |

`AIMM_API_KEY`, `AIMM_AUTH_SECRET`, and `POSTGRES_PASSWORD` have **no shipped default**.
Compose Postgres listens on **5433** (not 5432). If you set your own values in `.env`, those are used on every boot. Leave them empty
and run `python -m api.control_plane_secrets --write` (or `docker compose up`): unique
values are written to `.secrets/` (gitignored) once and reused. All Flow HTTP
routes except `GET /health` require `x-api-key`.

Atlas Cloud can be selected without replacing the existing OpenAI variables:

```bash
ATLASCLOUD_API_KEY=your-key
ATLASCLOUD_BASE_URL=https://api.atlascloud.ai/v1
ATLASCLOUD_MODEL=deepseek-ai/deepseek-v4-pro
```

The `ATLAS_CLOUD_API_KEY`, `ATLAS_CLOUD_BASE_URL`, and `ATLAS_CLOUD_MODEL`
spellings are accepted as aliases. `ATLASCLOUD_API_BASE` and
`ATLAS_CLOUD_API_BASE` are also accepted for the endpoint. Existing `OPENAI_*`
settings keep priority.

Budget-friendly API access: https://www.atlascloud.ai/console/coding-plan

[OrcaRouter](https://www.orcarouter.ai) can be selected the same way, without
replacing the existing OpenAI or Atlas Cloud variables:

```bash
ORCAROUTER_API_KEY=your-key
ORCAROUTER_BASE_URL=https://api.orcarouter.ai/v1
ORCAROUTER_MODEL=deepseek/deepseek-chat
```

OrcaRouter is an OpenAI-compatible AI gateway that exposes a provider/model
namespace across many models, with adaptive routing, automatic failover, and
gateway-level security. Existing `OPENAI_*` and `ATLASCLOUD_*` settings keep
priority when both are configured.

> **No LLM key → desk CoT and arbitrator overlay cannot run.** Weighted math still
> produces a decision. An LLM call without a key raises a clear error.

---

## Optional Environment Variables

### Strategy / agentic settings

**Not in `.env`.** Configure via `config/deploy.active.json` (see `docs/agentic-config.md`):

- `agents.*.weight` / `llm_enabled` / `enabled`
- `execution.use_llm_synthesis`
- `execution.arbitrator_llm`
- `execution.desk_debate_llm`
- `decision_threshold`

Optional path only: `AIMM_DEPLOY_CONFIG_PATH` selects which deploy JSON file to load.

### Safety / ops

| Variable                         | Effect                                  |
|----------------------------------|-----------------------------------------|
| `AIMM_RISK_GUARD_KILL_SWITCH`    | Emergency stop — blocks all trades      |
| `STRATEGY_INTERVAL_SEC`          | Graph run interval (default: 180)       |
| `AIMM_DEBUG_RISK`                | Verbose risk calculation logs           |

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
desk_debate ── [always on; LLM part from execution.desk_debate_llm]
signal_arbitrator ── [execution.use_llm_synthesis selects engine]
portfolio_proposal ── [always on]
desk_risk_guard ── [AIMM_RISK_GUARD_KILL_SWITCH]
portfolio_execute ── [MODE controls real vs paper]
audit ── [always on]
```

### Enabling/disabling agents via weight config

Setting an agent's weight to `0.0`, or omitting it from deploy JSON `agents`, disables it.
Omitted desks are skipped in the graph. Remaining enabled weights are re-normalized:

```python
weights = {"pattern_recognition_bot": 0.25, "technical_ta_engine": 0.30, "liquidity_order_flow": 0.15}
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
TWITTER_BEARER_TOKEN        ← Social sentiment (optional, experimental)
```

### Layer 1 — Agents (optional toggles)
```
AIMM_TA_TIER0_DISABLE      ← Technical TA
```

### Layer 2 — Arbitrator
```
deploy.active.json         ← Engine selection (use_llm_synthesis)
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
