import { NextResponse } from "next/server";
import { getPlatformAuthHeader } from "../../../_session";

export async function POST(_request: Request, context: { params: Promise<{ provider: string }> }) {
  const { provider } = await context.params;
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const headers = { ...(await getPlatformAuthHeader()) };
  const res = await fetch(
    `${flowApiBase}/admin/providers/${encodeURIComponent(provider)}/rotate-secret`,
    {
      method: "POST",
      headers,
    },
  );
  const json = await res.json().catch(() => ({}));
  return NextResponse.json(json, { status: res.status });
}
