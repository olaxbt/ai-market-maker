import { NextResponse } from "next/server";
import { flowApiBase } from "@/server/flowProxy";
import { flowAuthHeaders } from "@/app/api/_flowAuth";

/**
 * POST /api/futu/place-order
 *
 * Places a simulated paper order via the Futu OpenD backend.
 * Body: { symbol, side, qty, price, order_type }
 *
 * Returns the order result with status and order_id.
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { symbol, side, qty, price, order_type } = body as {
      symbol: string;
      side: "buy" | "sell";
      qty: number;
      price?: number;
      order_type?: "limit" | "market";
    };

    if (!symbol || !side || !qty) {
      return NextResponse.json(
        { error: "Missing required fields: symbol, side, qty" },
        { status: 400 },
      );
    }

    if (!["buy", "sell"].includes(side)) {
      return NextResponse.json(
        { error: "side must be 'buy' or 'sell'" },
        { status: 400 },
      );
    }

    // Try Flow backend first
    const flowBase = flowApiBase();
    try {
      const flowRes = await fetch(`${flowBase}/futu/place-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...flowAuthHeaders() },
        body: JSON.stringify({ symbol, side, qty, price, order_type: order_type ?? "limit" }),
        signal: AbortSignal.timeout(5000),
      });
      const data = await flowRes.json().catch(() => ({}));
      if (flowRes.ok) {
        return NextResponse.json(data);
      }
      return NextResponse.json(data, { status: flowRes.status });
    } catch (e) {
      return NextResponse.json(
        {
          error: "futu_flow_unreachable",
          detail: e instanceof Error ? e.message : String(e),
          flowBase,
        },
        { status: 503 },
      );
    }
  } catch (err: any) {
    return NextResponse.json(
      { error: `Failed to place order: ${err.message}` },
      { status: 500 },
    );
  }
}
