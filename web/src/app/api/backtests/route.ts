import { flowAuthHeaders } from "../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

/** Proxy: GET /backtests — list run_ids under .runs/backtests/ */
export async function GET() {
  return proxyJson(`${flowApiBase()}/backtests`, {
    headers: { ...flowAuthHeaders() },
    fallbackJson: { runs: [] },
  });
}
