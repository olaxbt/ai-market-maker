import { NextResponse } from "next/server";
import { setPlatformToken } from "../_session";

export async function POST(request: Request) {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const body = await request.json().catch(() => ({}));
  const res = await fetch(`${flowApiBase}/auth/register`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) return NextResponse.json(json, { status: res.status });
  if (typeof json?.token === "string") await setPlatformToken(json.token);
  return NextResponse.json({ ok: true });
}
