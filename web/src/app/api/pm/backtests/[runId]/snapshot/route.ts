import { flowAuthHeaders } from "../../../../_flowAuth";
import { flowApiBase, proxyJson } from "@/server/flowProxy";
import { NextRequest } from "next/server";

export async function GET(req: NextRequest, ctx: { params: Promise<{ runId: string }> }) {
  const { runId } = await ctx.params;
  const url = new URL(req.url);
  const llm = url.searchParams.get("llm");
  const upstream = new URL(`${flowApiBase().replace(/\/$/, "")}/pm/backtests/${runId}/snapshot`);
  if (llm) upstream.searchParams.set("llm", llm);
  return proxyJson(upstream.toString(), { headers: { ...flowAuthHeaders() } });
}
