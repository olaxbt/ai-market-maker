import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../../../../_flowAuth";

export async function GET(req: Request, ctx: { params: { runId: string } }) {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const runId = ctx.params.runId;
  const url = new URL(req.url);
  const llm = url.searchParams.get("llm");
  const upstream = new URL(`${flowApiBase.replace(/\/$/, "")}/pm/backtests/${runId}/snapshot`);
  if (llm) upstream.searchParams.set("llm", llm);

  try {
    const res = await fetch(upstream.toString(), {
      cache: "no-store",
      headers: { ...flowAuthHeaders() },
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Flow API unreachable", hint: flowApiBase },
      { status: 502 },
    );
  }
}

