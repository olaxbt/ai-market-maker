import { NextRequest } from "next/server";
import { flowApiBase, proxyJson, withSearchParams } from "@/server/flowProxy";

export async function GET(request: NextRequest) {
  const base = flowApiBase().replace(/\/?$/, "");
  const url = withSearchParams(`${base}/tools`, request);
  return proxyJson(url, {
    method: "GET",
    fallbackJson: { tools: [] },
  });
}

