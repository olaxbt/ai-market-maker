"use client";

import { useCallback, useEffect, useState } from "react";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";
import { FutuChart } from "./FutuChart";
import type { FutuBar } from "./FutuChart";

// ── Types ──

interface Ticker {
  symbol: string;
  name: string;
  market: string;
  lot: number;
  currency: string;
}

type IntervalOption = "1d" | "1w" | "1h";

const INTERVAL_OPTS: { label: string; value: IntervalOption }[] = [
  { label: "1h", value: "1h" },
  { label: "1d", value: "1d" },
  { label: "1w", value: "1w" },
];

const BAR_LIMIT = 200;

// ── Helpers ──

function fmtPrice(v: number | null | undefined, currency: string = "USD"): string {
  if (v == null) return "—";
  const symbol = currency === "HKD" ? "HK$" : "$";
  return `${symbol}${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtChange(delta: number | null): { text: string; color: string } {
  if (delta == null) return { text: "—", color: "text-[var(--nexus-muted)]" };
  const sign = delta >= 0 ? "+" : "";
  const color = delta >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.92)]";
  return { text: `${sign}${delta.toFixed(2)}%`, color };
}

function computeChange(bars: FutuBar[]): number | null {
  if (bars.length < 2) return null;
  const first = bars[0]?.close;
  const last = bars[bars.length - 1]?.close;
  if (!first || !last) return null;
  return ((last - first) / first) * 100;
}

// ── Component ──

export function FutuPage() {
  const [tickers, setTickers] = useState<Ticker[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>("HK.00700");
  const [interval, setInterval] = useState<IntervalOption>("1d");
  const [bars, setBars] = useState<FutuBar[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Selected ticker metadata
  const selectedTicker = tickers.find((t) => t.symbol === selectedSymbol);

  // Load ticker list
  useEffect(() => {
    async function loadTickers() {
      try {
        const res = await fetch("/api/futu/tickers", { cache: "no-store" });
        if (!res.ok) return;
        const data = await res.json();
        if (Array.isArray(data.tickers)) {
          setTickers(data.tickers);
        }
      } catch {
        // Silent — ticker list is static
      }
    }
    void loadTickers();
  }, []);

  // Load price bars
  const loadBars = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/futu/price?symbol=${encodeURIComponent(selectedSymbol)}&interval=${interval}&limit=${BAR_LIMIT}`,
        { cache: "no-store" },
      );
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error ?? `HTTP ${res.status}`);
      }
      const data = await res.json();
      const rawBars: number[][] = data.bars ?? [];
      const parsed: FutuBar[] = rawBars.map((b: number[]) => ({
        ts: b[0],
        open: b[1],
        high: b[2],
        low: b[3],
        close: b[4],
        volume: b[5],
      }));
      setBars(parsed);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load chart data");
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol, interval]);

  useEffect(() => {
    void loadBars();
  }, [loadBars]);

  const change = computeChange(bars);
  const changeDisplay = fmtChange(change);

  // Market split
  const hkTickers = tickers.filter((t) => t.market === "hk");
  const usTickers = tickers.filter((t) => t.market === "us");

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="FUTU OPEND"
        subtitle="HK & US stock market data via Futu OpenD gateway."
        active="nexus"
      />

      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {/* Controls bar */}
        <section className="flex flex-wrap items-center gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          {/* Market tabs */}
          <div className="flex w-full gap-6 sm:w-auto">
            <div className="min-w-0 flex-1 sm:min-w-[200px]">
              <div className="mb-1 text-[9px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                HK Stocks
              </div>
              <div className="flex flex-wrap gap-1">
                {hkTickers.map((t) => (
                  <button
                    key={t.symbol}
                    onClick={() => setSelectedSymbol(t.symbol)}
                    className={`rounded-lg px-2 py-1 text-[10px] font-medium transition-colors ${
                      selectedSymbol === t.symbol
                        ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]"
                        : "text-[rgba(138,149,166,0.6)] hover:text-white hover:bg-[rgba(255,255,255,0.04)]"
                    }`}
                  >
                    {t.name.split(" ")[0]}
                  </button>
                ))}
              </div>
            </div>
            <div className="min-w-0 flex-1 sm:min-w-[150px]">
              <div className="mb-1 text-[9px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                US Stocks
              </div>
              <div className="flex flex-wrap gap-1">
                {usTickers.map((t) => (
                  <button
                    key={t.symbol}
                    onClick={() => setSelectedSymbol(t.symbol)}
                    className={`rounded-lg px-2 py-1 text-[10px] font-medium transition-colors ${
                      selectedSymbol === t.symbol
                        ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]"
                        : "text-[rgba(138,149,166,0.6)] hover:text-white hover:bg-[rgba(255,255,255,0.04)]"
                    }`}
                  >
                    {t.name.split(" ")[0]}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Interval selector */}
          <div className="flex gap-1 ml-auto">
            {INTERVAL_OPTS.map((iv) => (
              <button
                key={iv.value}
                onClick={() => setInterval(iv.value)}
                className={`rounded-lg px-2.5 py-1 text-[10px] font-medium transition-colors ${
                  interval === iv.value
                    ? "bg-[rgba(99,102,241,0.12)] text-[rgba(99,102,241,0.85)]"
                    : "text-[rgba(138,149,166,0.5)] hover:text-white"
                }`}
              >
                {iv.label}
              </button>
            ))}
          </div>

          {/* Refresh */}
          <button
            onClick={() => void loadBars()}
            className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-1.5 text-[10px] text-[rgba(226,232,240,0.75)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </section>

        {/* Error banner */}
        {error && (
          <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        )}

        {/* Chart + Info */}
        <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_280px]">
          {/* Chart */}
          <section className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <div className="text-[11px] font-semibold text-[rgba(226,232,240,0.9)]">
                  {selectedTicker?.name ?? selectedSymbol}
                </div>
                <div className="text-[9px] text-[var(--nexus-muted)]">
                  {selectedSymbol} · {interval.toUpperCase()} · Lot {selectedTicker?.lot ?? 100}
                </div>
              </div>
              <div className="text-right">
                {bars.length > 0 && (
                  <>
                    <div className="text-[15px] font-bold tabular-nums text-white">
                      {fmtPrice(bars[bars.length - 1]?.close, selectedTicker?.currency)}
                    </div>
                    <div className={`text-[10px] font-medium tabular-nums ${changeDisplay.color}`}>
                      {changeDisplay.text}
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="relative">
              {loading && (
                <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-[rgba(6,8,11,0.5)]">
                  <div className="text-[11px] text-[var(--nexus-muted)]">Loading chart…</div>
                </div>
              )}
              <FutuChart
                bars={bars}
                symbol={selectedSymbol}
                height={420}
              />
            </div>
          </section>

          {/* Info panel */}
          <section className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
            <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)] mb-3">
              Market Info
            </div>

            {selectedTicker ? (
              <div className="space-y-3">
                <InfoRow label="Symbol" value={selectedTicker.symbol} />
                <InfoRow label="Name" value={selectedTicker.name} />
                <InfoRow label="Market" value={selectedTicker.market.toUpperCase()} />
                <InfoRow label="Lot Size" value={String(selectedTicker.lot)} />
                <InfoRow label="Currency" value={selectedTicker.currency} />
                <InfoRow
                  label="Bars"
                  value={String(bars.length)}
                />
                <InfoRow
                  label="Period (bars)"
                  value={`${interval} x ${bars.length}`}
                />
                {bars.length > 0 && (
                  <>
                    <hr className="border-[rgba(138,149,166,0.1)]" />
                    <InfoRow
                      label="High"
                      value={fmtPrice(Math.max(...bars.map((b) => b.high)), selectedTicker.currency)}
                    />
                    <InfoRow
                      label="Low"
                      value={fmtPrice(Math.min(...bars.map((b) => b.low)), selectedTicker.currency)}
                    />
                    <InfoRow
                      label="Avg Volume"
                      value={Math.round(bars.reduce((s, b) => s + b.volume, 0) / bars.length).toLocaleString()}
                    />
                  </>
                )}
              </div>
            ) : (
              <div className="text-[11px] text-[var(--nexus-muted)]">
                Select a ticker to view details.
              </div>
            )}

            {/* Order placement */}
            <div className="mt-6">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)] mb-2">
                Quick Order (Simulated)
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => placeSimulatedOrder(selectedSymbol, "buy", selectedTicker)}
                  className="flex-1 rounded-xl border border-[rgba(0,212,170,0.2)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[10px] font-medium text-[rgba(0,212,170,0.9)] hover:bg-[rgba(0,212,170,0.14)] transition-colors"
                >
                  Buy
                </button>
                <button
                  onClick={() => placeSimulatedOrder(selectedSymbol, "sell", selectedTicker)}
                  className="flex-1 rounded-xl border border-[rgba(242,92,84,0.2)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[10px] font-medium text-[rgba(242,92,84,0.85)] hover:bg-[rgba(242,92,84,0.14)] transition-colors"
                >
                  Sell
                </button>
              </div>
              <div className="mt-1 text-[8px] text-[var(--nexus-muted)] text-center">
                Paper trade · 1 lot · market price
              </div>
            </div>
          </section>
        </div>

        {/* Connection status */}
        <section className="mt-4 rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-[rgba(0,212,170,0.6)]" />
            <span className="text-[9px] text-[var(--nexus-muted)]">
              OpenD Gateway: Mock Mode · Configure FUTU_OPEND_HOST for live data
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}

// ── Sub-components ──

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-[var(--nexus-muted)]">{label}</span>
      <span className="text-[rgba(226,232,240,0.85)] font-mono tabular-nums">{value}</span>
    </div>
  );
}

// ── Mock order ──

async function placeSimulatedOrder(symbol: string, side: string, ticker?: Ticker) {
  try {
    const res = await fetch("/api/futu/place-order", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        symbol,
        side,
        qty: ticker?.lot ?? 100,
        order_type: "market",
      }),
    });
    const data = await res.json();
    if (data.status === "submitted") {
      // Dispatch a custom event so the console can show the order
      window.dispatchEvent(
        new CustomEvent("futu-order", {
          detail: { symbol, side, qty: ticker?.lot ?? 100, order_id: data.order_id, ts: Date.now() },
        }),
      );
    }
  } catch {
    // silent
  }
}
