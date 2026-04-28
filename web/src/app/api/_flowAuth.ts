/** Server-only: optional `x-api-key` for Flow API when `AIMM_API_KEY` is set (same name as Python). */
export function flowAuthHeaders(): Record<string, string> {
  const key = (process.env["AIMM_API_KEY"] ?? process.env["FLOW_API_KEY"] ?? "").trim();
  return key ? { "x-api-key": key } : {};
}
