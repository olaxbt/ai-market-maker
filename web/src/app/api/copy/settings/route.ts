import { getPlatformAuthHeader } from "../../platform/_session";
import { flowApiBase, proxyJson, withSearchParams } from "@/server/flowProxy";

export async function GET(request: Request) {
  const headers = { ...(await getPlatformAuthHeader()) };
  const target = withSearchParams(`${flowApiBase()}/copy/settings`, request);
  return proxyJson(target, { headers });
}

export async function POST(request: Request) {
  const bodyText = await request.text();
  const headers = { "content-type": "application/json", ...(await getPlatformAuthHeader()) };
  return proxyJson(`${flowApiBase()}/copy/settings`, { method: "POST", headers, body: bodyText });
}
