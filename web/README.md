# AI Market Maker — Web UI

**Modern React/Next.js dashboard** for the AI Market Maker agentic trading system.

This is the official frontend that provides **real-time visibility** into the agentic workflow: thought chains, desk reasoning, topology, signals, and Risk Guard decisions. It turns complex multi-agent execution into transparent, auditable "hedge fund desk" telemetry.

## Key Features

- **Nexus Star System** — Immersive 3D-like canvas with orbiting **AgentStars**, particle effects on new signals, and topology-based positioning (Kahn topological sort).
- **Live Agent Thought Stream** — Real-time trace cards showing reasoning, formulas, proposals, and vetoes.
- **Interactive Topology Panel** — Click any desk/node to filter the stream; active star highlights current focus.
- **Nexus Payload Visualization** — Full support for traces, metadata, topology, and message logs.
- **Smooth animations** powered by Framer Motion.
- **OpenClaw-ready** — Consumes the exact payload shape expected by external hosts and skill adapters.

Built to give developers, researchers, and future enterprise users full transparency into how agents collaborate and why decisions are made (or vetoed).

## Tech Stack

- **Next.js 14** (App Router)
- **Tailwind CSS**
- **Framer Motion** (animations & particles)
- **TypeScript**

## Quick Start

```bash
# From the project root
cd web

# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The UI will initially load **mock data**. Once the Python backend (`src/api`) is running on port 8001, it automatically connects to live traces and signals.

### Environment Variables (Optional)

Create a `.env.local` file if you need to override defaults:

```env
NEXT_PUBLIC_FLOW_API_BASE_URL=http://localhost:8001
NEXT_PUBLIC_FLOW_WS_URL=ws://localhost:8001
```

## Project Structure

```
web/
├── app/
│   └── page.tsx                 # Main shell + state management
├── components/
│   ├── NexusStarSystem/         # Canvas, CentralStar, AgentStar, particles
│   ├── NexusThoughtStreamPanel/
│   ├── AgentsConsoleView/
│   ├── NexusDeskView/
│   └── ...                      # Trace cards, topology widgets, HUD
├── hooks/
│   ├── useNexusPayload.ts
│   └── useNexusSignalCount.ts
├── lib/
│   └── api/
│       └── traces.ts            # Unified client for fetching/streaming NexusPayload
├── src/data/
│   └── mock-traces.json         # Rich 9-agent demo data
├── public/
└── schema/                      # Shared types from backend
```

## Data & Mock Mode

- **Mock data**: Located in `src/data/mock-traces.json` (includes full 9-agent topology, prompts, traces, and message log for realistic replay).
- Regenerate mock data: `npm run generate:mock`
- **Live mode**: The app automatically switches to real data when the backend exposes the `NexusPayload` endpoint or WebSocket stream.
- Schema reference: `../src/api/schema/nexus_payload.json` and `../schema/agent_trace.json`

## Roadmap & Legacy

- Current focus: Thought-chain transparency and topology interaction.
- Legacy static dashboard is preserved in the `ui/` folder for reference.
- Future plans: Prompt editing, backtest viewer integration, configurable layouts, and deeper OpenClaw host support.

See `../docs/nexus-nine-agents-rollout.md` for the broader agent rollout plan.

## Integration with Backend

The web app expects a `NexusPayload` shape containing:
- `topology`
- `traces[]`
- `metadata`
- `message_log[]` (for streaming feel)

It works out-of-the-box with the main project's FastAPI layer (`src/api/main:app`).