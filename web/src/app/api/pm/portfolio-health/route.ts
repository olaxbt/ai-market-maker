import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../../_flowAuth";

export async function GET() {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const upstream = new URL(`${flowApiBase.replace(/\/$/, "")}/pm/portfolio-health`);
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

