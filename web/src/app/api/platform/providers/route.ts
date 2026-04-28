import { NextResponse } from "next/server";
import { getPlatformAuthHeader } from "../_session";

export async function GET() {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const headers = { ...(await getPlatformAuthHeader()) };
  const res = await fetch(`${flowApiBase}/admin/providers`, {
    cache: "no-store",
    headers,
  });
  const json = await res.json().catch(() => ({}));
  return NextResponse.json(json, { status: res.status });
}

export async function POST(request: Request) {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const body = await request.json().catch(() => ({}));
  const headers = { "content-type": "application/json", ...(await getPlatformAuthHeader()) };
  const res = await fetch(`${flowApiBase}/admin/providers`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  return NextResponse.json(json, { status: res.status });
}
