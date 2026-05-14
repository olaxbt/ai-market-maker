import { NextResponse } from "next/server";

/**
 * GET /api/futu/tickers
 *
 * Returns the configured Futu universe tickers.
 * Reads from environment or returns a sensible default.
 */
export async function GET() {
  // Default HK and US stock universe
  const tickers = [
    // HK Stocks
    { symbol: "HK.00700", name: "Tencent Holdings", market: "hk", lot: 100, currency: "HKD" },
    { symbol: "HK.09988", name: "Alibaba Group", market: "hk", lot: 100, currency: "HKD" },
    { symbol: "HK.03690", name: "Meituan", market: "hk", lot: 100, currency: "HKD" },
    { symbol: "HK.09999", name: "NetEase", market: "hk", lot: 100, currency: "HKD" },
    { symbol: "HK.01810", name: "Xiaomi Corp", market: "hk", lot: 200, currency: "HKD" },
    { symbol: "HK.09618", name: "JD.com", market: "hk", lot: 50, currency: "HKD" },
    { symbol: "HK.02015", name: "Li Auto", market: "hk", lot: 100, currency: "HKD" },
    { symbol: "HK.01211", name: "BYD Company", market: "hk", lot: 500, currency: "HKD" },
    { symbol: "HK.02318", name: "Ping An Insurance", market: "hk", lot: 500, currency: "HKD" },
    { symbol: "HK.00388", name: "HKEX", market: "hk", lot: 100, currency: "HKD" },
    // US Stocks
    { symbol: "US.AAPL", name: "Apple Inc.", market: "us", lot: 1, currency: "USD" },
    { symbol: "US.MSFT", name: "Microsoft Corp.", market: "us", lot: 1, currency: "USD" },
    { symbol: "US.GOOGL", name: "Alphabet Inc.", market: "us", lot: 1, currency: "USD" },
    { symbol: "US.AMZN", name: "Amazon.com", market: "us", lot: 1, currency: "USD" },
    { symbol: "US.TSLA", name: "Tesla Inc.", market: "us", lot: 1, currency: "USD" },
  ];

  return NextResponse.json({ tickers });
}
