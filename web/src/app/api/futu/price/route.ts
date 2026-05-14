import { NextResponse } from "next/server";

/**
 * GET /api/futu/price?symbol=HK.00700&interval=1d&limit=200
 *
 * Fetches OHLCV bars from the Futu OpenD backend API.
 * Falls back to synthetic mock data when OpenD is not available.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") ?? "HK.00700";
  const interval = url.searchParams.get("interval") ?? "1d";
  const limit = parseInt(url.searchParams.get("limit") ?? "200", 10);

  try {
    // Try Flow backend first (if it has a futu proxy)
    const flowBase = process.env.FLOW_API_BASE_URL ?? "http://127.0.0.1:8001";
    const flowRes = await fetch(
      `${flowBase}/futu/price?symbol=${encodeURIComponent(symbol)}&interval=${interval}&limit=${limit}`,
      { cache: "no-store", signal: AbortSignal.timeout(3000) },
    );
    if (flowRes.ok) {
      const data = await flowRes.json();
      return NextResponse.json(data);
    }
  } catch {
    // Flow not available, fall through
  }

  // Fallback: synthetic mock data for demo purposes
  try {
    const bars = generateMockBars(symbol, limit);
    return NextResponse.json({ bars, symbol, source: "mock" });
  } catch (err: any) {
    return NextResponse.json(
      { error: `Failed to generate bars: ${err.message}` },
      { status: 502 },
    );
  }
}

/**
 * Generate deterministic mock OHLCV bars for Futu symbols.
 * In production these come from the Futu OpenD gateway via the backend.
 */
function generateMockBars(symbol: string, limit: number): number[][] {
  const now = Date.now();
  const basePrice = getBasePrice(symbol);
  const bars: number[][] = [];

  for (let i = 0; i < limit; i++) {
    const ts = now - (limit - i) * 86_400_000;
    const drift = Math.sin(i * 0.1) * basePrice * 0.05;
    const noise = (Math.random() - 0.5) * basePrice * 0.02;
    const o = basePrice + drift + noise;
    const h = o + Math.random() * basePrice * 0.015;
    const l = o - Math.random() * basePrice * 0.015;
    const c = o + (Math.random() - 0.48) * basePrice * 0.02;
    const v = Math.floor(1_000_000 + Math.random() * 5_000_000);
    bars.push([ts, o, h, l, c, v]);
  }

  return bars;
}

function getBasePrice(symbol: string): number {
  const prices: Record<string, number> = {
    "HK.00700": 380,    // Tencent
    "HK.09988": 85,     // Alibaba
    "HK.03690": 170,    // Meituan
    "HK.09999": 110,    // NetEase
    "HK.01810": 50,     // Xiaomi
    "HK.09618": 140,    // JD.com
    "HK.02015": 250,    // Li Auto
    "HK.01211": 280,    // BYD
    "HK.02318": 320,    // Ping An
    "HK.00388": 280,    // HKEX
    "US.AAPL": 180,     // Apple
    "US.MSFT": 420,     // Microsoft
    "US.GOOGL": 175,    // Alphabet
    "US.AMZN": 200,     // Amazon
    "US.TSLA": 180,     // Tesla
  };
  return prices[symbol] ?? 100;
}
