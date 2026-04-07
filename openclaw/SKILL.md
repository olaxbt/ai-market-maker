# AI Market Maker Skill

## Purpose

This skill provides tooling and documentation to run, inspect, and extend the multi-agent LangGraph trading workflow.

It includes a hard Risk Guard veto before any execution, structured tracing for transparency, and a simple HTTP API surface for external tools.

## When to Use

- Running or debugging the main LangGraph pipeline (`src/main.py`)
- Understanding how personas map to graph nodes (see `docs/personas/` and `src/api/payload_adapter.py`)
- Integrating with the Flow API (`/runs/*`, `/pm/*`, `/backtests`)

## Important Boundaries

- **Secrets**: Never pass sensitive data through LangChain serialization (`dumps`/`loads`). Keep `langchain-core` up to date.
- **Live Trading**: Currently focused on testnet/paper. Real execution requires explicit `live` mode + safety flags (planned for P3/P4).
- **Risk Guard**: This is a hard, code-level veto — not just an LLM suggestion.

## Flow API (for external tools)

The repo exposes a lightweight, mostly read-only HTTP API:

- `GET /runs/latest`          → Latest run data
- `GET /runs/{run_id}/payload` → Full payload of a run
- `GET /runs/{run_id}/events`  → Events and traces
- `GET /pm/portfolio-health`   → Portfolio summary
- `GET /backtests`             → List backtest runs

### Security

- If `AIMM_API_KEY` is not set → API is open (intended for local development only).
- If `AIMM_API_KEY` is set → All non-local requests require `x-api-key` header.
- In production, always put the Flow API behind a reverse proxy and configure `AIMM_CORS_ORIGINS` appropriately.

## Key Files

| Area                  | Location                                      |
|-----------------------|-----------------------------------------------|
| Main workflow         | `src/main.py`                                 |
| Core state schema     | `src/schemas/state.py`                        |
| Flow events & logging | `src/schemas/flow_events.py`, `src/flow_log.py` |
| Trace schemas         | `schema/agent_trace.json`                     |
| Web dashboard         | `web/` (Next.js)                              |

## Versioning & Stability

When changing tool schemas or breaking payload formats, bump the version in `manifest.json`.

Future tool names under the `nexus.*` namespace will remain stable for external integrations (OpenClaw / MCP).
