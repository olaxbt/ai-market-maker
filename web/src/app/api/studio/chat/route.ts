import { NextRequest } from "next/server";
import { flowApiBase, proxyJson } from "@/server/flowProxy";

export async function POST(request: NextRequest) {
  const base = flowApiBase().replace(/\/$/, "");
  const body = await request.json().catch(() => ({}));
  return proxyJson(`${base}/studio/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    fallbackJson: { steps: [{ action: "message", text: "Flow API unreachable." }] },
  });
}

