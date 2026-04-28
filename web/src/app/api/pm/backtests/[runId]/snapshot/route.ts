import { flowAuthHeaders } from "../../../../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function GET(req: Request, ctx: { params: { runId: string } }) {
  const runId = ctx.params.runId;
  const url = new URL(req.url);
  const llm = url.searchParams.get("llm");
  const upstream = new URL(`${flowApiBase().replace(/\/$/, "")}/pm/backtests/${runId}/snapshot`);
  if (llm) upstream.searchParams.set("llm", llm);
  return proxyJson(upstream.toString(), { headers: { ...flowAuthHeaders() } });
}
