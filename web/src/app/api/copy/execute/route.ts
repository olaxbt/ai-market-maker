import { getPlatformAuthHeader } from "../../platform/_session";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function POST(request: Request) {
  const bodyText = await request.text();
  const headers = { "content-type": "application/json", ...(await getPlatformAuthHeader()) };
  return proxyJson(`${flowApiBase()}/copy/execute`, { method: "POST", headers, body: bodyText });
}
