## Harness Memory + Run Receipts (Design Note)

This repo’s goal is to be **agentic without being a black box**.

To achieve that, we treat memory as a **harness-owned subsystem**:
- bounded (cost control)
- auditable (UI can show “what was reviewed and why”)
- schema’d (stable contract for prompts/tools)
- non-invasive (doesn’t require turning every node into a giant framework)

This design is run-scoped operational memory (what the system saw/decided/executed), **not** “personal preference memory”.

### References / inspiration

- **OpenClaw**: transparency-first memory (canonical artifacts you can inspect; no hidden magic).
- **Hermes / Mnemosyne**: “working memory” tier as bounded hot context, plus receipts/traces for replay/debugging.
- **LangGraph**: persistence via checkpointers/stores; we keep LangGraph state, but we also create artifacts that UIs can consume.

### What we store (working memory)

Working memory is intentionally small and recent:
- **recent_views**: what window/symbols the system looked at (evidence provenance)
- **recent_decisions**: compact stance/confidence summaries
- **recent_tool_events**: compact tool usage summaries (counts + tool names only)

Config lives in `config/app.default.json` under:

- `harness_memory.recent_views_max`
- `harness_memory.recent_decisions_max`
- `harness_memory.recent_tool_events_max`

### Where it lives in code

- `src/harness/run_memory.py`
  - `RunWorkingMemory`: bounded, serializable, run-scoped working memory
  - `IterationReceiptWriter`: append-only JSONL writer for per-step receipts

### Run receipts (iterations.jsonl)

For backtests, the system writes a per-bar receipt:

- Path: `.runs/backtests/<run_id>/iterations.jsonl`
- Each line is one JSON object (true JSONL), intended to be UI-friendly.

Receipt properties are intentionally compact and stable:
- `ts`, `run_id`, `symbol`
- `backtest`: cash/positions/window metadata
- `memory`: the working memory snapshot
- `decision`: stance/confidence (when available)
- `error`: present when the workflow fails at that bar (receipts must still exist)

This artifact is the “source of truth” for **what the system saw and why it acted**.

### Read-only API for UI/ops

To avoid adding “no value” endpoints, we expose only a read-only, bounded accessor:

- `GET /backtests/{run_id}/iterations?limit=...`

This is for Control Center UX and operator debugging.

### Control Center UX

`/control` includes “Run receipts (iterations)”:
- paste a `run_id`, load receipts
- show a recent tail (default: last 25 rows)
- highlight errors distinctly

### Non-goals (v1)

- Long-term user preference memory (e.g., “remember I like scalping”) — not this subsystem.
- Vector DB or hybrid retrieval — future work; only add when there is a clear UX need.
- Hidden “model magic” memory — everything must be inspectable via receipts/traces.

