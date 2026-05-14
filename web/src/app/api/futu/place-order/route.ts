import { NextResponse } from "next/server";

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
    const flowBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
    try {
      const flowRes = await fetch(`${flowBase}/futu/place-order`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ symbol, side, qty, price, order_type: order_type ?? "limit" }),
        signal: AbortSignal.timeout(5000),
      });
      if (flowRes.ok) {
        const data = await flowRes.json();
        return NextResponse.json(data);
      }
    } catch {
      // Flow not available, use mock response
    }

    // Mock response for demo
    const mockOrderId = `mock-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    return NextResponse.json({
      status: "submitted",
      order_id: mockOrderId,
      symbol,
      side,
      qty,
      price: price ?? null,
      order_type: order_type ?? "limit",
      trd_env: "SIMULATE",
      ts: Date.now(),
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: `Failed to place order: ${err.message}` },
      { status: 500 },
    );
  }
}
