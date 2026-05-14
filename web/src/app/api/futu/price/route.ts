import { NextResponse } from "next/server";
import { flowApiBase } from "@/server/flowProxy";
import { flowAuthHeaders } from "@/app/api/_flowAuth";

/**
 * GET /api/futu/price?symbol=HK.00700&interval=1d&limit=200
 *
 * Proxies to Flow `/futu/price` (Futu OpenD). Forwards HTTP errors instead of hiding them
 * behind synthetic bars. Sends `x-api-key` when `AIMM_API_KEY` is set (Flow may require it
 * for non-loopback clients, e.g. Next on host → Flow in Docker).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") ?? "HK.00700";
  const interval = url.searchParams.get("interval") ?? "1d";
  const limit = parseInt(url.searchParams.get("limit") ?? "200", 10);
  const flowBase = flowApiBase();

  try {
    const flowRes = await fetch(
      `${flowBase}/futu/price?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`,
      {
        cache: "no-store",
        signal: AbortSignal.timeout(15_000),
        headers: { ...flowAuthHeaders() },
      },
    );
    const data = (await flowRes.json().catch(() => ({}))) as Record<string, unknown>;
    if (flowRes.ok) {
      return NextResponse.json({ ...data, source: (data.source as string | undefined) ?? "flow" });
    }

    const hint401 =
      flowRes.status === 401
        ? "Flow has AIMM_API_KEY set; add the same AIMM_API_KEY to web/.env.local (or unset AIMM_API_KEY on the Flow process for local-only dev)."
        : undefined;

    return NextResponse.json(
      {
        error: "futu_upstream_error",
        httpStatus: flowRes.status,
        ...data,
        ...(hint401 ? { hint: hint401 } : {}),
      },
      { status: flowRes.status },
    );
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json(
      {
        error: "futu_flow_unreachable",
        detail: msg,
        flowBase,
        hint:
          "No response from Flow. Local dev: start uvicorn on 8001 and set FLOW_API_BASE_URL in web/.env.local. Docker: ensure the web service uses FLOW_API_BASE_URL=http://api:8001 (see docker-compose.prod.yml); host loopback in root .env breaks server-side proxying inside the web container.",
      },
      { status: 503 },
    );
  }
}
