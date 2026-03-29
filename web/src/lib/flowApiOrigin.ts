/**
 * Origin for direct browser → Flow API calls (backtests, equity series, etc.).
 * FastAPI enables CORS in `flow_stream_server.py`. Static export cannot ship
 * dynamic Next API routes; set `NEXT_PUBLIC_FLOW_API_BASE_URL` when the UI and API differ.
 */
export function getFlowApiOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_FLOW_API_BASE_URL?.trim() || "http://127.0.0.1:8001";
  return raw.replace(/\/$/, "");
}
