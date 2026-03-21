# Skill: AI Market Maker (Hedge Fund OS)

## Purpose

Operate and explain a **multi-agent trading workflow** with a **hard Risk Guard veto** before execution. Prefer **structured traces** (`thought_process`, proposals, veto) for transparency—aligned with the Nexus dashboard and `schema/agent_trace.json`.

## When to use

- Running or auditing the **LangGraph** pipeline (`src/main.py`).
- Mapping **personas** (`docs/personas/`) to **topology nodes** (`n1`–`n9`)—see `docs/persona_architecture_map.md`.
- Preparing **OpenClaw** tool calls against the future **NexusAdapter** (see `manifest.json` → `tools`).

## Boundaries

- **Secrets**: Never serialize untrusted dicts through LangChain `dumps`/`loads` with sensitive data; keep `langchain-core` patched (see `pyproject.toml`).
- **Live trading**: Execution is testnet-oriented today; production requires explicit mode flags and adapter work (roadmap P3/P4).
- **Veto**: Treat **Risk Guard** as **code-gated** (`risk_guard` node)—not a soft LLM suggestion.

## Key files

| Area | Location |
|------|----------|
| Workflow | `src/main.py` |
| State (target contract) | `src/schemas/state.py` |
| Flow events | `src/schemas/flow_events.py`, `src/flow_log.py` |
| Traces / UI contract | `schema/agent_trace.json`, `schema/nexus_payload.json` |
| Web dashboard | `web/` (Next.js) |

## Tool naming (future)

Use **stable names** from `openclaw/manifest.json` (`nexus.*`) so host runtimes can register MCP/OpenClaw tools without renames when the adapter lands.

## Versioning

Bump `manifest.json` → `version` when changing tool schemas or breaking payload fields.
