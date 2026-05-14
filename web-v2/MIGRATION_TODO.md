# Web → web-v2 migration checklist

This repo has **two different frontends**:

- `web/`: Next.js app-router with route handlers under `src/app/api/*` (proxies to the Python Flow API).
- `web-v2/`: Vite + React SPA (no server route handlers). It uses `react-router` for URL routing.

## API parity

`web/` relies on `/api/*` Next route handlers as **proxies** to Flow (default `http://127.0.0.1:8001`).

`web-v2/` uses:

- **Development:** Vite `server.proxy` in `vite.config.ts` — browser calls `/api/*`, Vite strips `/api` and forwards to `VITE_FLOW_API_BASE_URL` (see `.env.example`).
- **Production:** Same fetch paths (`/api/...`); deploy must reverse-proxy `/api` to Flow or set a gateway.

Environment variables: `VITE_FLOW_API_BASE_URL`, optional `VITE_FLOW_WS_URL` for Nexus live payload.

## UX / design principles (web-v2)

- **Single primary navigation:** the **left sidebar** lists app sections. The top bar is **only** a page title + mobile menu — no duplicate Leaderboard/Nexus/Studio strip in the main panel.
- **Console-only sub-nav:** on `/console`, a compact **tab strip** switches Topology / Agents / Research / Monitor (URL `?view=`). It does not replace sidebar navigation.
- **Control vs Backtests:** `/control` = Flow **diagnostics** (selftest, capabilities) + **harness memory** only. `/backtests` = **run** quick backtest (presets), **publish**, **receipts**, and saved run list — not mixed into Control Center.
- **Light & dark only** (no system auto): `next-themes` with `class` on `<html>`; **sidebar** toggle uses neutral muted styling (not primary/accent blue). Tokens in `src/styles/theme.css` (`:root` and `.dark`).

## Route parity (from `web/src/app/**/page.tsx`)

### Core

- [x] `/` → `/leaderboard`
- [x] `/leaderboard` → `LeaderboardV2OriginalPage`
- [x] `/studio` → `StudioV2Page` (session-based chat)
- [x] `/console` → `NexusView`
- [x] `/backtests` → `BacktestsPage`

### Migrated (real pages, not empty placeholders)

- [x] `/control` — Control Center (redesigned layout; Flow via `/api`)
- [x] `/get-started`, `/tools`, `/what-is-this`, `/trade`
- [x] `/platform/providers`, `/platform/login`
- [x] `/paper`, `/inbox`
- [x] `/backtest` (redirect)
- [x] `/account`
- [x] `/feed` (redirect)
- [x] `/studio/strategies` (redirect)
- [x] `/leaderboard/providers/:provider`
- [x] `/leadpage`, `/leadpage/providers/:provider` (redirects)
- [x] `/p/:provider`
- [x] `/agent/:nodeId`

### Legacy / dev routes

- [x] `/v2/chat`, `/v2/leaderboard` — kept for migration tooling

### Deeper parity (optional / larger effort)

- [ ] Next `/console` rich features: star-system intro, `BacktestLabPanel` + `SupervisorPanel` full grid, Recharts-heavy monitor — partially covered by v2 `NexusView` panels.
