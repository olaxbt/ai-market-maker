import { NextResponse } from "next/server";
import { flowAuthHeaders } from "../../../../_flowAuth";

export async function GET(request: Request, context: { params: Promise<{ provider: string }> }) {
  const { provider } = await context.params;
  const url = new URL(request.url);
  const params = url.searchParams.toString();

  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const target = `${flowApiBase}/leadpage/providers/${encodeURIComponent(provider)}/rows${
    params ? `?${params}` : ""
  }`;

  try {
    const res = await fetch(target, {
      cache: "no-store",
      headers: { ...flowAuthHeaders() },
    });
    const data = await res.json().catch(() => ({}));
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json(
      { error: "Flow API unreachable", hint: flowApiBase, provider, count: 0, rows: [] },
      { status: 502 },
    );
  }
}
