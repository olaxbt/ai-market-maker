import { flowAuthHeaders } from "../../../../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function POST(req: Request, ctx: { params: { runId: string } }) {
  const runId = ctx.params.runId;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  return proxyJson(`${flowApiBase().replace(/\/$/, "")}/pm/backtests/${runId}/ask`, {
    method: "POST",
    headers: { "content-type": "application/json", ...flowAuthHeaders() },
    body: JSON.stringify(body),
  });
}
