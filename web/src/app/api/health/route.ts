import { NextResponse } from "next/server";
import { flowApiBase } from "@/server/flowProxy";

/** Proxy: GET /api/health → Flow `/health` (includes llm_configured). */
export async function GET() {
  const flowBase = flowApiBase();
  try {
    const flowRes = await fetch(`${flowBase}/health`, { cache: "no-store" });
    const data = await flowRes.json().catch(() => ({}));
    return NextResponse.json(data, { status: flowRes.status });
  } catch {
    return NextResponse.json(
      { ok: false, llm_configured: false, error: "flow_unreachable", hint: flowBase },
      { status: 502 },
    );
  }
}
