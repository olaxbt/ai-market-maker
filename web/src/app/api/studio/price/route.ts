import { NextResponse } from "next/server";

/**
 * GET /api/studio/price?symbol=BTC/USDT&interval=1h&limit=200
 *
 * Fetches OHLCV bars via the backend Flow API (which uses CCXT).
 * Falls back to an ephemeral proxy that fetches directly from Binance public API
 * so paper-trading works without Flow running.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") ?? "BTC/USDT";
  const interval = url.searchParams.get("interval") ?? "1h";
  const limit = parseInt(url.searchParams.get("limit") ?? "200", 10);

  try {
    // Try Flow backend first
    const flowBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
    const flowRes = await fetch(
      `${flowBase}/studio/price?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`,
      { cache: "no-store", signal: AbortSignal.timeout(3000) },
    );
    if (flowRes.ok) {
      const data = await flowRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Flow not available, fall through
  }

  // Fallback: Binance public API
  try {
    const tfMap: Record<string, string> = {
      "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
      "1h": "1h", "4h": "4h", "1d": "1d", "1w": "1w",
    };
    const tf = tfMap[interval] ?? "1h";
    const binanceSymbol = symbol.replace("/", ""); // BTC/USDT → BTCUSDT

    const res = await fetch(
      `https://api.binance.com/api/v3/klines?symbol=${binanceSymbol}&interval=${tf}&limit=${limit}`,
      { signal: AbortSignal.timeout(5000) },
    );
    if (!res.ok) {
      return NextResponse.json(
        { error: `Binance returned ${res.status}` },
        { status: 502 },
      );
    }

    const klines: any[] = await res.json();
    const bars = klines.map((k: any) => [
      k[0],    // open time
      parseFloat(k[1]),  // open
      parseFloat(k[2]),  // high
      parseFloat(k[3]),  // low
      parseFloat(k[4]),  // close
      parseFloat(k[5]),  // volume
    ]);

    return NextResponse.json({ bars });
  } catch (err: any) {
    return NextResponse.json(
      { error: `Failed to fetch price data: ${err.message}` },
      { status: 502 },
    );
  }
}
