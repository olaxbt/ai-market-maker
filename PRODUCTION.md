## Production deployment (platform stack)

This repo can run as a small production platform:
- Postgres (results, signals, follows, inbox, executions)
- API service (FastAPI)
- Worker (fanout + optional auto-execute)
- Web dashboard (Next.js)

### Requirements
- Docker + Docker Compose
- A real `AIMM_AUTH_SECRET` (do not use dev fallback)

### Environment variables
Create a `.env` next to `docker-compose.prod.yml`:

```bash
# Database
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql+psycopg://aimm:${POSTGRES_PASSWORD}@db:5432/aimm

# Auth (required)
AIMM_ENV=production
AIMM_AUTH_SECRET=change-this-to-a-long-random-string

# Optional: protect API behind a shared key (recommended for internet exposure)
# If set, non-local requests to the API require x-api-key / Authorization: Bearer.
AIMM_API_KEY=

# Web -> API
FLOW_API_BASE_URL=http://api:8001

# CORS (set to your dashboard origin)
AIMM_CORS_ORIGINS=http://localhost:3000

# Worker
PLATFORM_WORKER_AUTO_EXECUTE=0
PLATFORM_WORKER_INTERVAL_SEC=2.0
PLATFORM_WORKER_BATCH=200
PLATFORM_WORKER_CURSOR=default
```

### Start

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

### Database migrations (recommended)

Run once (or on each release) before starting traffic:

```bash
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head
```

Notes:
- The runtime DB auto-create is disabled in production compose (`AIMM_DB_AUTOCREATE=0`).
- If you want dev convenience, set `AIMM_DB_AUTOCREATE=1` locally.

### Operational endpoints
- API health: `GET /health`
- Latest run payload: `GET /runs/latest/payload`
- Leaderboard: `GET /leadpage/leaderboard`
- Feed: `GET /signals/feed`

### Security checklist
- Set `AIMM_AUTH_SECRET` and keep it private
- Put the API behind a reverse proxy with TLS
- Set `AIMM_CORS_ORIGINS` to your real dashboard origin
- If exposed publicly, set `AIMM_API_KEY` and restrict network ingress
- Keep `PLATFORM_WORKER_AUTO_EXECUTE=0` unless you explicitly want it

