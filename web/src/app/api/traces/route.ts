import { NextResponse } from "next/server";
import mockTraces from "@/data/mock-traces.json";
import { flowApiBase } from "@/server/flowProxy";
import { flowAuthHeaders } from "../_flowAuth";

/** Live Flow by default. Set USE_MOCK=1 or NEXT_PUBLIC_USE_MOCK=1 to serve bundled demo JSON from /api/traces. */
function useMockTraces(): boolean {
  const u = process.env.USE_MOCK?.trim();
  const p = process.env.NEXT_PUBLIC_USE_MOCK?.trim();
  return u === "1" || p === "1";
}

export async function GET() {
  if (useMockTraces()) {
    return NextResponse.json(mockTraces, {
      headers: { "x-flow-data-source": "mock" },
    });
  }

  const allowMockFallback =
    (process.env.FLOW_ALLOW_MOCK_FALLBACK ??
      process.env.NEXT_PUBLIC_FLOW_ALLOW_MOCK_FALLBACK ??
      "1") === "1";
  const flowOrigin = flowApiBase();

  try {
    const res = await fetch(`${flowOrigin}/runs/latest/payload`, {
      cache: "no-store",
      headers: { ...flowAuthHeaders() },
    });
    if (!res.ok) {
      if (allowMockFallback) {
        return NextResponse.json(mockTraces, {
          headers: { "x-flow-data-source": "mock-fallback" },
        });
      }
      return NextResponse.json(
        {
          error: `Flow API returned ${res.status}`,
          hint: "Start the Flow API, set FLOW_ALLOW_MOCK_FALLBACK=1, or set USE_MOCK=1 / NEXT_PUBLIC_USE_MOCK=1 for bundled demo topology.",
        },
        { status: 502 },
      );
    }
    const json = await res.json();
    return NextResponse.json(json, {
      headers: {
        "x-flow-data-source": "live",
        "x-flow-api-base-url": flowOrigin,
      },
    });
  } catch {
    if (allowMockFallback) {
      return NextResponse.json(mockTraces, {
        headers: { "x-flow-data-source": "mock-fallback" },
      });
    }
    return NextResponse.json(
      {
        error: "Flow API is unreachable",
        hint: "Start the Flow API, set FLOW_ALLOW_MOCK_FALLBACK=1, or set USE_MOCK=1 / NEXT_PUBLIC_USE_MOCK=1 for bundled demo topology.",
      },
      { status: 502 },
    );
  }
}
