#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

FLOW_API_PORT="${FLOW_API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3000}"
MODE="${MODE:-paper}"
RUN_STRATEGY="${RUN_STRATEGY:-1}"

# Basic dependency checks (fail fast with a useful message).
need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: missing required command: $1" >&2
    return 1
  fi
}
need_cmd uv
need_cmd curl
need_cmd npm

# Default ticker comes from versioned config (config/app.default.json).
if [[ -z "${TICKER:-}" ]]; then
  TICKER="$(
    uv run python -c 'from config.app_settings import load_app_settings; print(load_app_settings().market.default_ticker)'
  )"
fi

# Warn if live mode is requested without the explicit allow gate.
if [[ "${MODE}" == "live" ]]; then
  if [[ "${AI_MARKET_MAKER_ALLOW_LIVE:-}" != "1" && "${AI_MARKET_MAKER_ALLOW_LIVE:-}" != "true" && "${AI_MARKET_MAKER_ALLOW_LIVE:-}" != "yes" ]]; then
    echo "WARNING: MODE=live but AI_MARKET_MAKER_ALLOW_LIVE is not set to 1/true/yes." >&2
    echo "  The Python runner is expected to refuse live execution without this." >&2
  fi
fi

# Paper mode defaults (UI + Supervisor expect a consistent starting balance).
export AIMM_PAPER_START_USDT="${AIMM_PAPER_START_USDT:-10000}"

# UI payload trimming (prevents huge WS payloads and UI lag on long runs).
export AIMM_UI_TAIL_EVENTS="${AIMM_UI_TAIL_EVENTS:-1200}"
export AIMM_UI_TAIL_TRACES="${AIMM_UI_TAIL_TRACES:-350}"
export AIMM_UI_TAIL_MESSAGES="${AIMM_UI_TAIL_MESSAGES:-600}"

# Safety cap for on-disk flow event logs (prevents .runs from growing without bound).
export AIMM_FLOW_LOG_MAX_MB="${AIMM_FLOW_LOG_MAX_MB:-50}"

# Seconds between full graph runs (default 180 from config.cadence — reduce token burn).
if [[ -z "${STRATEGY_INTERVAL_SEC:-}" ]]; then
  STRATEGY_INTERVAL_SEC="$(
    uv run python -c 'from config.cadence import load_strategy_interval_sec; print(load_strategy_interval_sec())'
  )"
fi
export STRATEGY_INTERVAL_SEC
uv run python -c \
  "from config.cadence import warn_if_aggressive_cadence; warn_if_aggressive_cadence(${STRATEGY_INTERVAL_SEC})"

echo "Starting AI Market Maker dev stack..."
echo "  API: http://127.0.0.1:${FLOW_API_PORT}"
echo "  Web: http://127.0.0.1:${WEB_PORT}"
echo "  Strategy loop: ${RUN_STRATEGY} (mode=${MODE}, ticker=${TICKER}, interval=${STRATEGY_INTERVAL_SEC}s)"

cleanup() {
  echo ""
  echo "Stopping services..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

uv run python -m uvicorn api.main:app --reload --port "${FLOW_API_PORT}" &
API_PID=$!
echo "API PID: ${API_PID}"

# Next.js proxies to the Flow API; if the browser loads before uvicorn is listening,
# /api/traces returns 502. Wait for health before starting the web dev server.
FLOW_HEALTH_URL="http://127.0.0.1:${FLOW_API_PORT}/health"
API_WAIT_SEC="${API_WAIT_SEC:-60}"
echo "Waiting for Flow API (${FLOW_HEALTH_URL})..."
for ((i = 1; i <= API_WAIT_SEC; i++)); do
  if curl -sf "${FLOW_HEALTH_URL}" >/dev/null 2>&1; then
    echo "Flow API is ready (${i}s)."
    break
  fi
  sleep 1
  if [[ "${i}" -eq "${API_WAIT_SEC}" ]]; then
    echo "WARNING: Flow API did not become ready in ${API_WAIT_SEC}s."
    echo "  Web will still start; refresh after uvicorn is up, or rely on client retries."
  fi
done

if [[ "${RUN_STRATEGY}" == "1" ]]; then
  (
    while true; do
      uv run python src/main.py --mode "${MODE}" --ticker "${TICKER}" || true
      sleep "${STRATEGY_INTERVAL_SEC}"
    done
  ) &
  STRAT_PID=$!
  echo "Strategy loop PID: ${STRAT_PID}"
fi

(
  cd web
  FLOW_API_BASE_URL="http://127.0.0.1:${FLOW_API_PORT}" \
  NEXT_PUBLIC_FLOW_API_BASE_URL="http://127.0.0.1:${FLOW_API_PORT}" \
  NEXT_PUBLIC_FLOW_WS_URL="ws://127.0.0.1:${FLOW_API_PORT}" \
  NEXT_PUBLIC_USE_MOCK=0 \
  npm run dev -- --port "${WEB_PORT}"
) &
WEB_PID=$!
echo "Web PID: ${WEB_PID}"

wait

