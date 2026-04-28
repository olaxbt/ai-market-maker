import { getPlatformAuthHeader } from "../../platform/_session";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function GET() {
  const headers = { ...(await getPlatformAuthHeader()) };
  return proxyJson(`${flowApiBase()}/paper/snapshot`, {
    headers,
    fallbackJson: { snapshot: null },
  });
}
