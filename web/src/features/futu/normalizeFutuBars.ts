import type { FutuBar } from "./FutuChart";

/** Deterministic [0,1) pseudo-random from symbol + bar index (stable mock charts). */
export function futuDemoNoise(symbol: string, i: number): number {
  let h = 0;
  for (let k = 0; k < symbol.length; k++) h = (h * 31 + symbol.charCodeAt(k)) >>> 0;
  const x = Math.sin((h % 1000) * 12.9898 + i * 78.233) * 43758.5453;
  return x - Math.floor(x);
}

/**
 * Flow / mock APIs may emit timestamps in seconds or ms, and bars newest-first.
 * Normalize for the chart: ms timestamps, ascending time, valid OHLC ordering.
 */
export function normalizeFutuBars(raw: number[][]): FutuBar[] {
  const rows: FutuBar[] = [];

  for (const b of raw) {
    if (!Array.isArray(b) || b.length < 6) continue;
    let ts = Number(b[0]);
    if (!Number.isFinite(ts)) continue;
    // Seconds vs ms: Futu / Unix often seconds (~1.7e9); JS Date is ms (~1.7e12)
    if (ts > 0 && ts < 1e11) ts = Math.round(ts * 1000);

    let open = Number(b[1]);
    let high = Number(b[2]);
    let low = Number(b[3]);
    let close = Number(b[4]);
    const volume = Number.isFinite(Number(b[5])) ? Math.max(0, Math.round(Number(b[5]))) : 0;
    if (![open, high, low, close].every((x) => Number.isFinite(x))) continue;

    const maxOhlc = Math.max(open, high, low, close);
    const minOhlc = Math.min(open, high, low, close);
    high = maxOhlc;
    low = minOhlc;

    rows.push({ ts, open, high, low, close, volume });
  }

  rows.sort((a, b) => a.ts - b.ts);

  const byTs = new Map<number, FutuBar>();
  for (const row of rows) {
    byTs.set(row.ts, row);
  }
  return Array.from(byTs.values()).sort((a, b) => a.ts - b.ts);
}
