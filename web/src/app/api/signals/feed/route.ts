import { flowAuthHeaders } from "../../_flowAuth";
import { flowApiBase, proxyJson, withSearchParams } from "@/server/flowProxy";

export async function GET(request: Request) {
  const target = withSearchParams(`${flowApiBase()}/signals/feed`, request);
  return proxyJson(target, {
    headers: { ...flowAuthHeaders() },
    fallbackJson: { count: 0, signals: [] },
  });
}
