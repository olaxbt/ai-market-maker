import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../../_flowAuth";

function flowBase(): string {
  return process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
}

export async function GET(_req: Request, { params }: { params: { nodeId: string } }) {
  const base = flowBase();
  const nodeId = decodeURIComponent(params.nodeId);
  const res = await fetch(`${base}/agent-prompts/${encodeURIComponent(nodeId)}`, {
    cache: "no-store",
    headers: { ...flowAuthHeaders() },
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}

export async function PUT(req: Request, { params }: { params: { nodeId: string } }) {
  const base = flowBase();
  const nodeId = decodeURIComponent(params.nodeId);
  const body = await req.text();
  const res = await fetch(`${base}/agent-prompts/${encodeURIComponent(nodeId)}`, {
    method: "PUT",
    headers: { "content-type": "application/json", ...flowAuthHeaders() },
    body,
  });
  const text = await res.text();
  return new NextResponse(text, {
    status: res.status,
    headers: { "content-type": res.headers.get("content-type") ?? "application/json" },
  });
}
