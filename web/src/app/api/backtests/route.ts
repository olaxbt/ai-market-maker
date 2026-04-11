import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../_flowAuth";

/** Proxy: GET /backtests — list run_ids under .runs/backtests/ */
export async function GET() {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  try {
    const res = await fetch(`${flowApiBase}/backtests`, {
      cache: "no-store",
      headers: { ...flowAuthHeaders() },
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Flow API unreachable", hint: flowApiBase, runs: [] },
      { status: 502 },
    );
  }
}
