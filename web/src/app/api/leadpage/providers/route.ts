import { flowAuthHeaders } from "../../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function GET() {
  return proxyJson(`${flowApiBase()}/leadpage/providers`, {
    headers: { ...flowAuthHeaders() },
    fallbackJson: { providers: ["local"] },
  });
}
