import { getPlatformAuthHeader } from "../../platform/_session";
import { flowApiBase, proxyJson, withSearchParams } from "@/server/flowProxy";

export async function GET(request: Request) {
  const headers = { ...(await getPlatformAuthHeader()) };
  const target = withSearchParams(`${flowApiBase()}/social/inbox`, request);
  return proxyJson(target, { headers, fallbackJson: { items: [] } });
}
