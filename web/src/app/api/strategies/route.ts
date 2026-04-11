import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../_flowAuth";

/** Proxy: GET /strategies — list Quant strategy presets from the Flow API. */
export async function GET() {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  try {
    const res = await fetch(`${flowApiBase}/strategies`, {
      cache: "no-store",
      headers: { ...flowAuthHeaders() },
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { strategies: [], error: "Flow API unreachable" },
      { status: 502 },
    );
  }
}
