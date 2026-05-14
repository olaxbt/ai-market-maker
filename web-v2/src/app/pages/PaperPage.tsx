import { useEffect, useState } from "react";
import { Link } from "react-router";
import { LoginRequiredPanel } from "../components/LoginRequiredPanel";

type Snapshot = {
  account_id: string;
  instrument: string;
  cash_usdt: number;
  realized_pnl_usdt: number;
  positions: Record<string, unknown>[];
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

export default function PaperPage({ embedded = false }: { embedded?: boolean }) {
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
        fetch("/api/paper/snapshot", { cache: "no-store" as any }),
        fetch("/api/paper/trades?limit=200", { cache: "no-store" as any }),
      ]);
      const sJson = await sRes.json().catch(() => ({}));
      const tJson = await tRes.json().catch(() => ({}));
      if (sRes.status === 401 || tRes.status === 401) {
        setLoginRequired(true);
        setSnapshot(null);
        setTrades([]);
        return;
      }
      if (!sRes.ok) throw new Error((sJson as any)?.detail || (sJson as any)?.error || "Failed to load snapshot");
      if (!tRes.ok) throw new Error((tJson as any)?.detail || (tJson as any)?.error || "Failed to load trades");
      setSnapshot((sJson as any)?.snapshot ?? null);
      setTrades(Array.isArray((tJson as any)?.trades) ? (tJson as any).trades : []);
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
    <div className={embedded ? "px-4 pb-10 sm:px-6" : "flex-1 min-h-0 overflow-auto px-6 py-10"}>
      <div className={embedded ? "mx-auto w-full max-w-6xl" : "mx-auto w-full max-w-6xl"}>
        {embedded ? null : (
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Paper Book</div>
              <h1 className="mt-1 text-[18px] font-semibold">Per-user paper snapshot + fills</h1>
              <p className="mt-1 text-[12px] text-muted-foreground">
                This is your personal paper portfolio. Sign in to view balances, positions, and fills.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/ops?tab=queue" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
                Queue
              </Link>
              <Link
                to="/platform/providers"
                className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
              >
                Providers
              </Link>
            </div>
          </div>
        )}

        {loginRequired ? (
          <div className="mt-4">
            <LoginRequiredPanel body="Sign in to view balances, positions, and fills." />
          </div>
        ) : null}

        {embedded && (loading || loginRequired) ? null : (
          <section className="mt-4 rounded-2xl border border-border bg-card p-4">
            <div className="text-[12px] text-muted-foreground">
              {loading ? "Loading…" : snapshot ? `account=${snapshot.account_id} instrument=${snapshot.instrument}` : ""}
            </div>
            {error ? (
              <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                {error}
              </div>
            ) : null}
          </section>
        )}

        {snapshot ? (
          <section className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="text-[11px] font-semibold">Summary</div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-[12px]">
                <div className="rounded-xl border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground">Cash (USDT)</div>
                  <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.cash_usdt)}</div>
                </div>
                <div className="rounded-xl border border-border bg-muted/20 p-3">
                  <div className="text-[11px] text-muted-foreground">Realized PnL (USDT)</div>
                  <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.realized_pnl_usdt)}</div>
                </div>
                <div className="col-span-2 text-[11px] text-muted-foreground">Updated: {fmtTs(snapshot.updated_ts)}</div>
              </div>
            </div>

            <div className="rounded-2xl border border-border bg-card p-4">
              <div className="text-[11px] font-semibold">Positions</div>
              {asPositions(snapshot).length === 0 ? (
                <div className="mt-2 text-[12px] text-muted-foreground">No open positions.</div>
              ) : (
                <div className="mt-2 overflow-auto">
                  <table className="w-full min-w-[420px] border-separate border-spacing-0 text-left text-[12px]">
                    <thead className="sticky top-0 z-10 bg-background">
                      <tr className="text-[11px] text-muted-foreground">
                        <th className="px-3 py-2">Symbol</th>
                        <th className="px-3 py-2">Qty</th>
                        <th className="px-3 py-2">Avg entry</th>
                      </tr>
                    </thead>
                    <tbody>
                      {asPositions(snapshot).map((p) => (
                        <tr key={p.symbol} className="border-t border-border hover:bg-muted/20">
                          <td className="px-3 py-2">{p.symbol}</td>
                          <td className="px-3 py-2 font-mono tabular-nums">
                            {p.qty.toLocaleString(undefined, { maximumFractionDigits: 6 })}
                          </td>
                          <td className="px-3 py-2 font-mono tabular-nums">
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

        <section className="mt-3 rounded-2xl border border-border bg-card p-4">
          <div className="text-[11px] font-semibold">Recent fills</div>
          {loginRequired ? (
            <div className="mt-2 text-[12px] text-muted-foreground">Sign in to view fills.</div>
          ) : trades.length === 0 ? (
            <div className="mt-2 text-[12px] text-muted-foreground">No fills yet.</div>
          ) : (
            <div className="mt-2 overflow-auto">
              <table className="w-full min-w-[720px] border-separate border-spacing-0 text-left text-[12px]">
                <thead className="sticky top-0 z-10 bg-background">
                  <tr className="text-[11px] text-muted-foreground">
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
                      <tr key={`${t.ts ?? "x"}:${t.symbol ?? "y"}:${idx}`} className="border-t border-border hover:bg-muted/20">
                        <td className="px-3 py-2 text-muted-foreground">{fmtTs(t.ts)}</td>
                        <td className="px-3 py-2">{t.symbol ?? "—"}</td>
                        <td className="px-3 py-2">{t.side ?? "—"}</td>
                        <td className="px-3 py-2 font-mono tabular-nums">
                          {typeof t.qty === "number" ? t.qty.toLocaleString(undefined, { maximumFractionDigits: 6 }) : "—"}
                        </td>
                        <td className="px-3 py-2 font-mono tabular-nums">
                          {typeof t.price === "number" ? t.price.toLocaleString(undefined, { maximumFractionDigits: 6 }) : "—"}
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

