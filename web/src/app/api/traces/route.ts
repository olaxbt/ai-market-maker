import { NextResponse } from "next/server";
import mockTraces from "@/data/mock-traces.json";
import { flowAuthHeaders } from "../_flowAuth";

export async function GET() {
  const useMock = (process.env.USE_MOCK ?? process.env.NEXT_PUBLIC_USE_MOCK ?? "0") === "1";
  if (useMock) {
    return NextResponse.json(mockTraces);
  }

  const allowMockFallback =
    (process.env.FLOW_ALLOW_MOCK_FALLBACK ??
      process.env.NEXT_PUBLIC_FLOW_ALLOW_MOCK_FALLBACK ??
      "0") === "1";
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";

  try {
    const res = await fetch(`${flowApiBase}/runs/latest/payload`, {
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
          hint: "Start backend stream server or set USE_MOCK=1 for demo mode.",
        },
        { status: 502 },
      );
    }
    const json = await res.json();
    return NextResponse.json(json, {
      headers: {
        "x-flow-data-source": "live",
        "x-flow-api-base-url": flowApiBase,
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
        hint: "Start backend stream server or set USE_MOCK=1 for demo mode.",
      },
      { status: 502 },
    );
  }
}
