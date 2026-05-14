import { NextResponse } from "next/server";

type ProxyOptions = {
  method?: string;
  headers?: Record<string, string>;
  cache?: RequestCache;
  body?: string;
  fallbackJson?: Record<string, unknown>;
};

/**
 * Base URL for Next.js **server** routes when proxying to Flow (FastAPI).
 *
 * Prefer `FLOW_API_BASE_URL` (e.g. `http://api:8001` in Docker). If unset, use
 * `NEXT_PUBLIC_FLOW_API_BASE_URL` so local `npm run dev` works when only the public
 * var is set in `web/.env.local`.
 */
export function flowApiBase(): string {
  const raw =
    process.env.FLOW_API_BASE_URL?.trim() ||
    process.env.NEXT_PUBLIC_FLOW_API_BASE_URL?.trim() ||
    "http://127.0.0.1:8001";
  return raw.replace(/\/$/, "");
}

export function proxyUnreachable(fallbackJson: Record<string, unknown>) {
  return NextResponse.json(
    { error: "Flow API unreachable", hint: flowApiBase(), ...fallbackJson },
    { status: 502 },
  );
}

export async function proxyJson(targetUrl: string, opts: ProxyOptions = {}) {
  try {
    const res = await fetch(targetUrl, {
      method: opts.method,
      headers: opts.headers,
      body: opts.body,
      cache: opts.cache ?? "no-store",
    });
    const json = await res.json().catch(() => ({}));
    return NextResponse.json(json, { status: res.status });
  } catch {
    return proxyUnreachable(opts.fallbackJson ?? {});
  }
}

export function withSearchParams(targetBase: string, request: Request): string {
  const url = new URL(request.url);
  const params = url.searchParams.toString();
  return `${targetBase}${params ? `?${params}` : ""}`;
}
