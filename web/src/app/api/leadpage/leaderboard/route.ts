import { flowAuthHeaders } from "../../_flowAuth";
import { flowApiBase, proxyJson, withSearchParams } from "@/server/flowProxy";

export async function GET(request: Request) {
  const target = withSearchParams(`${flowApiBase()}/leadpage/leaderboard`, request);
  return proxyJson(target, {
    headers: { ...flowAuthHeaders() },
    fallbackJson: { count: 0, rows: [] },
  });
}
