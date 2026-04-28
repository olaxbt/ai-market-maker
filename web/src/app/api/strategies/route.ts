import { flowAuthHeaders } from "../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

/** Proxy: GET /strategies — list Quant strategy presets from the Flow API. */
export async function GET() {
  return proxyJson(`${flowApiBase()}/strategies`, {
    headers: { ...flowAuthHeaders() },
    fallbackJson: { strategies: [] },
  });
}
