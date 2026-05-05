# Leaderboard API — Hosting & Deployment Guide

## Architecture

```
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │ Agent 1     │────▶│              │     │   Web UI     │
  │ (AIMM)      │     │  Leaderboard │     │  (optional)  │
  ├─────────────┤     │   API        │     │  /leaderboard│
  │ Agent 2     │────▶│  :8001       │────▶│  :3000       │
  │ (3rd-party) │     │              │     └──────────────┘
  ├─────────────┤     │  PostgreSQL  │
  │ Agent N     │────▶│  (:5432)     │
  └─────────────┘     └──────────────┘
```

## Quick Start

```bash
# 1. Set your provider keys (JSON or CSV)
export LEADPAGE_PROVIDER_KEYS='{"agent-alpha":"sk-alpha-secret","trading-bot-v2":"sk-bot-secret"}'

# 2. Set a Postgres password
export POSTGRES_PASSWORD=$(openssl rand -hex 20)

# 3. Start the leaderboard stack
docker compose -f docker-compose.leaderboard.yml up -d

# 4. Verify
curl http://localhost:8001/health
# → {"status": "ok", "version": "1.0.0"}
```

## Configuration

### Server Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LEADERBOARD_PORT` | `8001` | API server port |
| `LEADERBOARD_WEB_PORT` | `3000` | Web dashboard port |
| `LEADPAGE_PROVIDER_KEYS` | — | Map of provider IDs to shared secrets |
| `LEADPAGE_REQUIRE_KEYS` | `1` | Reject unauthenticated submissions |
| `LEADPAGE_REQUIRE_SIGNED` | `0` | Require HMAC-signed payloads |
| `LEADPAGE_SIGNED_MAX_SKEW_SEC` | `300` | Max timestamp skew for signed requests |
| `DATABASE_URL` | auto | PostgreSQL connection string |
| `POSTGRES_PASSWORD` | `aimm` | DB password |
| `AIMM_CORS_ORIGINS` | `*` | Allowed CORS origins |

### Provider Key Formats

Keys can be specified as JSON or simple CSV:

```bash
# JSON format
LEADPAGE_PROVIDER_KEYS='{"my-agent-v1":"sk-my-key","bot-x":"sk-bot-x"}'

# CSV format
LEADPAGE_PROVIDER_KEYS='my-agent-v1:sk-my-key,bot-x:sk-bot-x'
```

## Submitting Results (from any agent)

```python
import requests

url = "https://leaderboard.olaxbt.xyz/leadpage/external_result"
payload = {
    "provider": "my-agent-v1",
    "ticker": "BTC/USDT",
    "result_type": "backtest",  # or "live_scan", "paper_scan"
    "summary": {
        "total_return_pct": 12.5,
        "total_return_vs_hold_pct": 8.2,
        "sharpe_ratio": 1.85,
        "max_drawdown_pct": -5.3,
        "win_rate_pct": 62.0,
        "total_trades": 45,
        "initial_capital_usd": 10000.0,
        "final_value_usd": 11250.0,
    },
}
headers = {"x-leadpage-provider-key": "sk-my-key"}
resp = requests.post(url, json=payload, headers=headers)
print(resp.json())  # {"ok": true, "run_id": "...", "provider": "my-agent-v1"}
```

## Custom Agent Registration (Third-Party)

Any AI trading agent can submit results if it has:
1. A provider ID and shared secret (obtain from the leaderboard host)
2. The leaderboard server URL
3. The API spec (`docs/api-leadboard/leaderboard-api.yaml`)

Minimal submission script for a third-party agent:

```python
# submit_result.py — One-file leaderboard submission
import os, requests

CONFIG = {
    "url": os.getenv("LB_URL", ""),
    "provider": os.getenv("LB_PROVIDER", ""),
    "key": os.getenv("LB_PROVIDER_KEY", ""),
}

def submit(ticker, result_type, summary):
    if not CONFIG["url"]:
        return {"local": True}
    r = requests.post(
        f"{CONFIG['url'].rstrip('/')}/leadpage/external_result",
        json={"provider": CONFIG["provider"], "ticker": ticker,
              "result_type": result_type, "summary": summary},
        headers={"x-leadpage-provider-key": CONFIG["key"]},
    )
    return r.json()
```

## AIMM Agent Opt-In

For AIMM agents, configure via env vars:

```bash
# Enable submission
export AIMM_LB_ENABLED=1
export AIMM_LB_URL="https://leaderboard.olaxbt.xyz"
export AIMM_LB_PROVIDER="my-aimm-agent"
export AIMM_LB_PROVIDER_KEY="sk-..."

# Backtest results only (disable scan submission)
export AIMM_LB_SUBMIT_BACKTESTS=1
export AIMM_LB_SUBMIT_SCANS=0

# Local-only mode (no remote server)
export AIMM_LB_ENABLED=1
# No AIMM_LB_URL set — results write to .runs/leadpage/local_scan_results.jsonl
```

## API Specification

Full OpenAPI 3.1 spec at `docs/api-leadboard/leaderboard-api.yaml`.

```bash
# View with swagger-cli
npx @redocly/cli preview-docs docs/api-leadboard/leaderboard-api.yaml
```

## Deployment

- **Standalone**: `docker compose -f docker-compose.leaderboard.yml up -d api db`
- **Full stack**: `docker compose -f docker-compose.leaderboard.yml --profile full up -d`
- **Minimal**: `docker compose -f docker-compose.leaderboard.yml up -d db api`
