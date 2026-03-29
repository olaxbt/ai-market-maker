#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

FLOW_API_PORT="${FLOW_API_PORT:-8001}"
WEB_PORT="${WEB_PORT:-3000}"
TICKER="${TICKER:-BTC/USDT}"
MODE="${MODE:-paper}"
RUN_STRATEGY="${RUN_STRATEGY:-1}"

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

