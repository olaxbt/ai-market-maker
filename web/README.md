# AI Market Maker — Web (Agentic Nexus UI)

React UI for real-time **agent thought-chain** transparency (core value of Agentic Nexus / OpenClaw).

## Stack

- **Next.js 14** (App Router)
- **Tailwind CSS**
- **Framer Motion** (animations)
- **Agent trace schema** from `schema/agent_trace.json` / `src/schemas/agent_trace.py`

## Layout (code organization)

- **`app/page.tsx`**: Shell only — view mode, selection state, `useNexusPayload` / `useNexusSignalCount`.
- **`components/`**: `NexusConsoleHeader`, `NexusDeskView`, `AgentsConsoleView`, `NexusThoughtStreamPanel`, trace/topology/star widgets.
- **`hooks/`**: Data loading and signal-count demo logic.
- **`lib/api/traces.ts`**: Single client entry for `NexusPayload` fetch (swap URL when backend is live).

## Features

- **Nexus Star System** (`NexusStarSystem`): `rounded-3xl` space panel; **canvas ring field**; **CentralStar** + **AgentStar** + **StarParticle** (Framer) per expert layout; agent **% orbit** from **topology order** (Kahn sort); **HUD** clock line. Particles when `signalCount` increments (`useNexusSignalCount`).
- **Agent thought stream**: `AgentTraceCard` per trace (thought chain, formula, proposal, veto).
- **Topology panel**: Click nodes to filter the stream; active star follows selection or `ACTIVE` node in payload.
- **OpenClaw-ready**: Payload matches `metadata` + `topology` + `traces` (see `src/types/nexus-payload.ts`).

## Run

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Data

- **Mock**: `src/data/mock-traces.json` — **9-agent** topology, `traces[]`, full **`agent_prompts[]`** (system/task/COT + model/tools), and flat **`message_log[]`** for stream-style replay / Nexus demo bumps. Regenerate with `npm run generate:mock`.
- **Schema**: `../src/api/schema/nexus_payload.json` (payload envelope); trace rows still align with `../schema/agent_trace.json` where applicable.
- **Rollout plan**: `../docs/nexus-nine-agents-rollout.md`.
- **Live**: Point the app at an API that returns the same `NexusPayload` shape (or stream `message_log` lines + traces).

## Legacy UI

The previous static dashboard (nexus canvas, KPI bar, event stream) remains in the **`ui/`** folder. The **`web/`** app is the canonical front end for agent thought-chain transparency.
