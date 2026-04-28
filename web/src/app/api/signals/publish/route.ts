import { flowAuthHeaders } from "../../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function POST(request: Request) {
  const bodyText = await request.text();
  return proxyJson(`${flowApiBase()}/signals/publish`, {
    method: "POST",
    headers: { "content-type": "application/json", ...flowAuthHeaders() },
    body: bodyText,
  });
}
