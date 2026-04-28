import { NextResponse } from "next/server";
import { getPlatformAuthHeader } from "../../platform/_session";

export async function GET() {
  const flowApiBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
  const headers = { ...(await getPlatformAuthHeader()) };
  const res = await fetch(`${flowApiBase}/social/following`, { cache: "no-store", headers });
  const json = await res.json().catch(() => ({}));
  return NextResponse.json(json, { status: res.status });
}
