import { NextResponse } from "next/server";
import { getPlatformAuthHeader } from "../../platform/_session";

export async function POST(request: Request) {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const bodyText = await request.text();
  const headers = { "content-type": "application/json", ...(await getPlatformAuthHeader()) };
  const res = await fetch(`${flowApiBase}/social/unfollow`, {
    method: "POST",
    headers,
    body: bodyText,
  });
  const json = await res.json().catch(() => ({}));
  return NextResponse.json(json, { status: res.status });
}
