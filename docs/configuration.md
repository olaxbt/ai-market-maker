## Configuration

Default settings live in versioned JSON files under the `config/` folder.

Use `.env` **only** for secrets, API endpoints, and run mode. Strategy and policy values should stay in git.
`.env` is loaded for local development defaults only; if a variable is already set in your environment, it takes precedence.

### Why config-first + env override is good practice

This repo uses a **config-first** approach for non-secret defaults (checked into git), with **environment variables**
as *optional overrides*.

- **Reproducibility**: a tagged commit + `config/*.json` fully describes default behavior.
- **Reviewability**: behavior changes show up in diffs/PR review instead of being hidden in shell history.
- **Deployment friendliness**: env overrides remain available for containerized deployments and emergency toggles.
- **Secret hygiene**: `.env` stays focused on secrets/endpoints rather than “random tuning knobs.”

### Run artifacts (`.runs/`) retention

Runs and backtests write artifacts under `.runs/`. To prevent multi-GB accumulation, the project enforces a
simple retention policy after each run:

- **`runs.max_total_mb`**: cap total disk usage under `.runs/` (default: `500`)
- **`runs.keep_last`**: keep at least this many newest artifacts (default: `200`)
- **`runs.index.max_mb`**: cap `.runs/index.jsonl` size (default: `25`)
- **`runs.index.keep_last`**: keep last N index rows (default: `20000`)

Optional env overrides (emergency / one-off):

- `AIMM_RUNS_MAX_TOTAL_MB`
- `AIMM_RUNS_KEEP_LAST`
- `AIMM_RUNS_BACKTESTS_MAX_TOTAL_MB`
- `AIMM_RUNS_BACKTESTS_KEEP_LAST`

Backtests retention is **disabled by default** to avoid surprising deletions. Enable it in `config/app.default.json`:

- `runs.backtests.retention_enabled: true`

### Evaluation export (benchmarking)

To compare runs in a spreadsheet or against other projects, export the compact ledger plus backtest summaries:

```bash
uv run python -m eval_export --runs-dir .runs -o exports/evaluation --format csv
uv run aimm-export-eval -o exports/evaluation.csv
```

Parquet output needs the optional extra: `uv sync --extra export` (installs `pyarrow`). The combined table uses `record_kind` to distinguish `index` rows (from `.runs/index.jsonl`) from `backtest` rows (from `.runs/backtests/<id>/summary.json`).

### Flow logging detail

To keep `.runs/*.events.jsonl` useful but not bloated, flow reasoning events can be compacted:

- `flow.detail: full | standard | compact` (default: `standard`)
  - `full`: include tool results and larger blobs (best for deep debugging; biggest logs)
  - `standard`: omit large tool result payloads but keep tool call metadata
  - `compact`: keep only the high-signal decision fields; drop bulky context

### Paper trading and backtest: spot vs mock perp (leverage)

Paper mode and multi-step backtests can simulate **spot** (full-cash) or a **USDT-linear perp-style** account with **initial margin ≈ notional / leverage**. This is a research mock (no funding, liquidation engine, or venue queue semantics); it exists so results are comparable when others run the same config.

- **`paper.instrument`**: `"spot"` (default) or `"perp"`.
- **`paper.leverage`**: used when `instrument` is `"perp"` (clamped against `fund_policy.max_leverage` where applicable).

For CLI backtests, `src/backtest/run_demo.py` accepts **`--instrument spot|perp`** and **`--leverage`** (defaults follow `config/app.default.json` / `load_app_settings().paper` when omitted).

### Quick Start

```bash
uv run python -u src/main.py --ticker BTC/USDT
```

### Agent prompt configuration (optional)

Some LLM nodes support operator-configurable prompt settings via `config/agent_prompts` (see code: `config/agent_prompts.py`).
This is useful when you want to tweak tone/verbosity/tools without editing the graph logic.

### LLM mode (agentic nodes)

LLM-driven nodes (like the Tier-2 `signal_arbitrator`) are enabled automatically when `OPENAI_API_KEY` is set,
or explicitly when `AIMM_LLM_MODE=1`.

#### Structured output enforcement (recommended)

To keep trading signals reliable, the `signal_arbitrator` uses **schema-constrained prompting** plus a
**validate + retry** loop. This prevents malformed JSON from silently degrading into default `HOLD`.

Defaults live in `config/app.default.json` under `llm`, and can be overridden via environment variables.

Environment variables (optional overrides):

- **`AIMM_LLM_OUTPUT_RETRIES`**: Number of retries when the model output fails validation (default: `2`, max: `5`)
- **`AIMM_LLM_STRICT_JSON`**: If `1`, append strict “JSON only” requirements to the arbitrator prompt (default: `1`)

The run payload includes:

- `proposed_signal.params.llm_attempts`
- `proposed_signal.params.llm_retry_reasons`
- `proposed_signal.params.llm_json_parse_ok`
- `proposed_signal.params.llm_validation_warnings`

The portfolio LLM proposal also records:

- `proposal.llm_attempts`
- `proposal.llm_retry_reasons`

The portfolio LLM execution plan also records:

- `execution.llm_attempts`
- `execution.llm_retry_reasons`