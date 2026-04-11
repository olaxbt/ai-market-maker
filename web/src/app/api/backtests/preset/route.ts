import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../../_flowAuth";

/** Proxy to Flow API: POST /backtests/preset (named Quant strategy preset). */
export async function POST(req: Request) {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }
  try {
    const res = await fetch(`${flowApiBase}/backtests/preset`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...flowAuthHeaders() },
      body: JSON.stringify(body),
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
