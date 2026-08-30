# Agentic configuration

Primary source of truth: `config/deploy.active.json`.

Secrets stay in `.env` (API keys, exchange credentials, DB).
**Deploy JSON is the single source of truth for strategy** — there are no env overrides for arbitrator mode, LLM agent lists, or desk debate.

## Schema

```json
{
  "description": "Human note. Ignored by trading logic; copied into backtest reports.",
  "profile": { "profile_id": "g49_tilt" },
  "agents": {
    "technical_ta_engine": { "weight": 0.35, "llm_enabled": true, "enabled": true },
    "monetary_sentinel": { "weight": 0.20, "llm_enabled": false, "enabled": true },
    "news_narrative_miner": { "weight": 0.20, "llm_enabled": true, "enabled": true },
    "pattern_recognition_bot": { "weight": 0.15, "llm_enabled": false, "enabled": true },
    "statistical_alpha_engine": { "weight": 0.10, "llm_enabled": false, "enabled": true }
  },
  "execution": {
    "use_llm_synthesis": true,
    "desk_debate_llm": false,
    "arbitrator_llm": true,
    "allows_short": true,
    "leverage": 2.0
  },
  "decision_threshold": {
    "buy": { "min_composite": 53, "min_confidence": 16 },
    "sell": { "max_composite": 41, "min_confidence": 26 },
    "alignment_gating": { "enabled": true, "min_factors_for_directional": 2 },
    "ta_led": { "enabled": true, "agent_id": "technical_ta_engine" }
  }
}
```

Agent keys (only these):

- `monetary_sentinel`, `news_narrative_miner`
- `pattern_recognition_bot`, `statistical_alpha_engine`, `technical_ta_engine`
- `retail_hype_tracker`, `pro_bias_analyst`
- `whale_behavior_analyst`, `liquidity_order_flow`

## LLM control

Desk CoT and the final arbitrator overlay are independent. Weighted math always runs first (static `agents.*.weight`). LLM overlays fall back to that math on failure. Alignment gating still blocks a directional LLM override.

| Field | Effect |
|-------|--------|
| `agents.*.llm_enabled` | That desk may call the model (`infer_agent`) |
| `execution.use_llm_synthesis` | Master switch for **per-desk** LLM enrichment |
| `execution.arbitrator_llm` | LLM overlay on the final BUY/SELL/HOLD **after** weighted math |
| `execution.desk_debate_llm` | LLM turns in desk debate (kept off in shipped presets) |

`use_llm_synthesis` does not turn on the arbitrator overlay. `arbitrator_llm` does not turn on desk CoT. Both need an API key (`OPENAI_API_KEY`, `ATLASCLOUD_API_KEY`, or `ORCAROUTER_API_KEY`).

| Preset | Role |
|--------|------|
| `deploy.active.json` | Rank 1 earner (g49): +8.15% / 1.71 |
| `deploy.easy_short.json` … `deploy.sharpe_focus.json` | Ranks 2–10 unique earners |
| `deploy.ohlcv_only.json` | No-LLM CI smoke |

See [`docs/paper-eval.md`](paper-eval.md) for the ranked table.

Weights are one-time config in `agents.*.weight` (Config Designer / deploy JSON). They are not retuned each bar.

Fewer agents / selective `llm_enabled` is how you control desk cost. Turn `arbitrator_llm` off for measurement backtests.

Omitted or `"enabled": false` desks are **not added to the LangGraph** — they do not run, not just zero-weight.

## Config Designer (outside the graph)

| Endpoint | Purpose |
|----------|---------|
| `GET /config-designer/styles` | List presets |
| `POST /config-designer/style` | Seed a preset |
| `POST /config-designer/review` | Validate deploy JSON |
| `POST /config-designer/chat` | Design chat |

Presets: `macro_tilt`, `ohlcv_measurement`, `conservative`.  
Shortcut without LLM: message `style: macro_tilt`.
