"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LoginRequiredPanel } from "@/components/LoginRequiredPanel";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

type Snapshot = {
  account_id: string;
  instrument: string;
  cash_usdt: number;
  realized_pnl_usdt: number;
  positions: Record<string, unknown>[];
  spot_positions?: Record<string, unknown>[];
  perp_positions?: Record<string, unknown>[];
  updated_ts: number;
};

type Trade = Record<string, unknown>;

function fmtMoney(v: unknown) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtTs(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function asPositions(snapshot: Snapshot | null): Array<{ symbol: string; qty: number; avg_entry: number }> {
  if (!snapshot) return [];
  const rows = Array.isArray(snapshot.positions) ? snapshot.positions : [];
  const out: Array<{ symbol: string; qty: number; avg_entry: number }> = [];
  for (const r of rows) {
    if (!r || typeof r !== "object") continue;
    const o = r as Record<string, unknown>;
    const symbol = typeof o.symbol === "string" ? o.symbol : "";
    const qty = typeof o.qty === "number" ? o.qty : Number(o.qty);
    const avg = typeof o.avg_entry === "number" ? o.avg_entry : Number(o.avg_entry);
    if (!symbol || !Number.isFinite(qty) || !Number.isFinite(avg)) continue;
    out.push({ symbol, qty, avg_entry: avg });
  }
  return out.sort((a, b) => a.symbol.localeCompare(b.symbol));
}

function asTrades(trades: Trade[]): Array<{ ts?: number; symbol?: string; side?: string; qty?: number; price?: number }> {
  const out: Array<{ ts?: number; symbol?: string; side?: string; qty?: number; price?: number }> = [];
  for (const t of trades) {
    if (!t || typeof t !== "object") continue;
    const o = t as Record<string, unknown>;
    const ts = typeof o.ts === "number" ? o.ts : typeof o.created_ts === "number" ? o.created_ts : undefined;
    const symbol = typeof o.symbol === "string" ? o.symbol : typeof o.ticker === "string" ? o.ticker : undefined;
    const side = typeof o.side === "string" ? o.side : undefined;
    const qty = typeof o.qty === "number" ? o.qty : undefined;
    const price = typeof o.price === "number" ? o.price : undefined;
    out.push({ ts, symbol, side, qty, price });
  }
  return out;
}

export function PaperAccountPage() {
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loginRequired, setLoginRequired] = useState(false);

  async function load() {
    setLoading(true);
    setError(null);
    setLoginRequired(false);
    try {
      const [sRes, tRes] = await Promise.all([
        fetch("/api/paper/snapshot", { cache: "no-store" }),
        fetch("/api/paper/trades?limit=200", { cache: "no-store" }),
      ]);
      const sJson = await sRes.json().catch(() => ({}));
      const tJson = await tRes.json().catch(() => ({}));
      if (sRes.status === 401 || tRes.status === 401) {
        setLoginRequired(true);
        setSnapshot(null);
        setTrades([]);
        return;
      }
      if (!sRes.ok) throw new Error(sJson?.detail || sJson?.error || "Failed to load snapshot");
      if (!tRes.ok) throw new Error(tJson?.detail || tJson?.error || "Failed to load trades");
      setSnapshot(sJson?.snapshot ?? null);
      setTrades(Array.isArray(tJson?.trades) ? tJson.trades : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load paper account");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    const t = window.setInterval(load, 10_000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="PAPER BOOK"
        subtitle="Per-user paper account snapshot and fills."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {loginRequired ? (
          <LoginRequiredPanel body="Your paper book is per-user. Sign in to view balances, positions, and fills." />
        ) : null}
        <section className="mt-3 flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="text-[11px] text-[var(--nexus-muted)]">
            {loading
              ? "Loading…"
              : snapshot
                ? `account=${snapshot.account_id} instrument=${snapshot.instrument}`
                : "—"}
          </div>

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
          <div className="flex items-center gap-2">
            <Link
              href="/inbox"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Inbox
            </Link>
            <Link
              href="/platform/providers"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Providers
            </Link>
          </div>
        </section>

        {snapshot ? (
          <section className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Summary
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-[rgba(226,232,240,0.9)]">
                <div className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(0,0,0,0.18)] p-3">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                    Cash (USDT)
                  </div>
                  <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.cash_usdt)}</div>
                </div>
                <div className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(0,0,0,0.18)] p-3">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                    Realized PnL (USDT)
                  </div>
                  <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.realized_pnl_usdt)}</div>
                </div>
                <div className="col-span-2 text-[10px] text-[var(--nexus-muted)]">
                  Updated: {fmtTs(snapshot.updated_ts)}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Positions
              </div>
              {asPositions(snapshot).length === 0 ? (
                <div className="mt-2 text-[11px] text-[var(--nexus-muted)]">No open positions.</div>
              ) : (
                <div className="mt-2 overflow-auto">
                  <table className="w-full min-w-[420px] border-separate border-spacing-0 text-left text-[11px]">
                    <thead className="sticky top-0 z-10 bg-[rgba(6,8,11,0.85)] backdrop-blur">
                      <tr className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                        <th className="px-3 py-2">Symbol</th>
                        <th className="px-3 py-2">Qty</th>
                        <th className="px-3 py-2">Avg entry</th>
                      </tr>
                    </thead>
                    <tbody>
                      {asPositions(snapshot).map((p) => (
                        <tr
                          key={p.symbol}
                          className="border-t border-[rgba(138,149,166,0.12)] hover:bg-[rgba(255,255,255,0.02)]"
                        >
                          <td className="px-3 py-2 text-[rgba(226,232,240,0.92)]">{p.symbol}</td>
                          <td className="px-3 py-2 font-mono tabular-nums text-[rgba(226,232,240,0.9)]">
                            {p.qty.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                          </td>
                          <td className="px-3 py-2 font-mono tabular-nums text-[rgba(226,232,240,0.9)]">
                            {p.avg_entry.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </section>
        ) : null}

        <section className="mt-3 rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
            Recent fills
          </div>
          {trades.length === 0 ? (
            <div className="mt-2 text-[11px] text-[var(--nexus-muted)]">No fills yet.</div>
          ) : (
            <div className="mt-2 overflow-auto">
              <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-[11px]">
                <thead className="sticky top-0 z-10 bg-[rgba(6,8,11,0.85)] backdrop-blur">
                  <tr className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                    <th className="px-3 py-2">When</th>
                    <th className="px-3 py-2">Symbol</th>
                    <th className="px-3 py-2">Side</th>
                    <th className="px-3 py-2">Qty</th>
                    <th className="px-3 py-2">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {asTrades(trades)
                    .slice(-50)
                    .reverse()
                    .map((t, idx) => (
                      <tr
                        key={`${t.ts ?? "x"}:${t.symbol ?? "y"}:${idx}`}
                        className="border-t border-[rgba(138,149,166,0.12)] hover:bg-[rgba(255,255,255,0.02)]"
                      >
                        <td className="px-3 py-2 text-[var(--nexus-muted)]">{fmtTs(t.ts)}</td>
                        <td className="px-3 py-2 text-[rgba(226,232,240,0.92)]">{t.symbol ?? "—"}</td>
                        <td className="px-3 py-2 text-[rgba(226,232,240,0.9)]">{t.side ?? "—"}</td>
                        <td className="px-3 py-2 font-mono tabular-nums text-[rgba(226,232,240,0.9)]">
                          {typeof t.qty === "number"
                            ? t.qty.toLocaleString(undefined, { maximumFractionDigits: 6 })
                            : "—"}
                        </td>
                        <td className="px-3 py-2 font-mono tabular-nums text-[rgba(226,232,240,0.9)]">
                          {typeof t.price === "number"
                            ? t.price.toLocaleString(undefined, { maximumFractionDigits: 6 })
                            : "—"}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
