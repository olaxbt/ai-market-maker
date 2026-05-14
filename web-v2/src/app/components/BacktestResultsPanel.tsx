import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type BacktestSummary = {
  run_id?: string;
  metrics?: Record<string, unknown>;
  start_ts?: number | null;
  end_ts?: number | null;
  start_iso?: string | null;
  end_iso?: string | null;
};

type EquityPoint = {
  ts?: number;
  t?: number;
  equity?: number;
  value?: number;
};

type TradeRow = {
  ts?: number;
  created_ts?: number;
  symbol?: string;
  ticker?: string;
  side?: string;
  direction?: number;
  qty?: number;
  size?: number;
  amount?: number;
  price?: number;
  entry_price?: number;
  fill_price?: number;
};

function asNum(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

export function BacktestResultsPanel({ runId }: { runId: string | null }) {
  const rid = (runId ?? "").trim() || null;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [equity, setEquity] = useState<EquityPoint[] | null>(null);
  const [trades, setTrades] = useState<TradeRow[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!rid) {
        setLoading(false);
        setError(null);
        setSummary(null);
        setEquity(null);
        setTrades(null);
        return;
      }
      setLoading(true);
      setError(null);
      setSummary(null);
      setEquity(null);
      setTrades(null);
      try {
        const base = `/api/backtests/${encodeURIComponent(rid)}`;
        const [sRes, eRes, tRes] = await Promise.all([
          fetch(`${base}/summary`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/equity?max_points=2000`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/trades?limit=2000`, { cache: "no-store" as RequestCache }),
        ]);
        const sJson = (await sRes.json().catch(() => ({}))) as BacktestSummary;
        const eJson = (await eRes.json().catch(() => ({}))) as { points?: EquityPoint[] };
        const tJson = (await tRes.json().catch(() => ({}))) as { trades?: TradeRow[] };
        if (!sRes.ok) {
          throw new Error((sJson as any)?.detail || (sJson as any)?.error || `Failed to load summary (${sRes.status})`);
        }
        if (cancelled) return;
        setSummary(sJson);
        setEquity(Array.isArray(eJson?.points) ? eJson.points : []);
        setTrades(Array.isArray(tJson?.trades) ? tJson.trades : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Failed to load results");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [rid]);

  const metrics = (summary?.metrics ?? {}) as Record<string, unknown>;
  const mSharpe = asNum(metrics?.sharpe) ?? asNum(metrics?.sharpe_ratio);
  const mReturn = asNum(metrics?.total_return_pct);
  const mMaxDd = asNum(metrics?.max_drawdown_pct);
  const mWinRate = asNum(metrics?.win_rate) ?? asNum(metrics?.win_rate_pct);
  const mTrades = asNum(metrics?.trade_count) ?? asNum(metrics?.total_trades);

  const timeRange = useMemo(() => {
    const sIso = (summary as any)?.start_iso;
    const eIso = (summary as any)?.end_iso;
    if (typeof sIso === "string" && typeof eIso === "string" && sIso && eIso) return { s: sIso, e: eIso };
    const sTs = (summary as any)?.start_ts;
    const eTs = (summary as any)?.end_ts;
    if (typeof sTs === "number" && typeof eTs === "number") return { s: new Date(sTs).toISOString(), e: new Date(eTs).toISOString() };
    return null;
  }, [summary]);

  const chartData = useMemo(() => {
    const pts = equity ?? [];
    return pts.map((p, idx) => ({
      x: typeof p.ts === "number" ? p.ts : typeof p.t === "number" ? p.t : idx,
      equity: typeof p.equity === "number" ? p.equity : typeof p.value === "number" ? p.value : null,
    }));
  }, [equity]);

  const recentTrades = useMemo(() => {
    const rows = Array.isArray(trades) ? trades : [];
    const norm = rows
      .map((t) => {
        const ts = typeof t.ts === "number" ? t.ts : typeof t.created_ts === "number" ? t.created_ts : null;
        const symbol = (t.symbol || t.ticker || "").toString();
        const sideRaw = (t.side || "").toString().toUpperCase();
        const side =
          sideRaw ||
          (typeof t.direction === "number" ? (t.direction >= 0 ? "BUY" : "SELL") : "");
        const rawQty =
          typeof t.qty === "number"
            ? t.qty
            : typeof t.size === "number"
              ? t.size
              : typeof t.amount === "number"
                ? t.amount
                : null;
        const rawPrice =
          typeof t.price === "number"
            ? t.price
            : typeof t.entry_price === "number"
              ? t.entry_price
              : typeof t.fill_price === "number"
                ? t.fill_price
                : null;
        const qty = typeof rawQty === "number" ? rawQty : null;
        const price = typeof rawPrice === "number" ? rawPrice : null;
        return { ts, symbol, side, qty, price };
      })
      .filter((t) => t.symbol || t.side || t.qty != null || t.price != null);
    return norm.slice(-40).reverse();
  }, [trades]);

  function fmtTs(tsSec: number | null) {
    if (tsSec == null || !Number.isFinite(tsSec)) return "—";
    try {
      return new Date(tsSec * 1000).toLocaleString();
    } catch {
      return "—";
    }
  }

  return (
    <Card>
      <CardHeader className="border-b">
        <CardTitle className="text-base">Backtest results</CardTitle>
        <CardDescription>
          {rid ? (
            <>
              run <code className="font-mono text-xs">{rid}</code>
              {timeRange ? (
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  {timeRange.s.replace("T", " ").replace("Z", "Z")} → {timeRange.e.replace("T", " ").replace("Z", "Z")}
                </span>
              ) : null}
            </>
          ) : (
            "Select a saved run or run a new backtest."
          )}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-4">
        {!rid ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-10 text-center text-sm text-muted-foreground">
            No run selected.
          </div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Loading performance…</div>
        ) : error ? (
          <div className="rounded-md border border-destructive/35 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : (
          <div className="space-y-4">
            <div className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Return %</div>
                <div className="font-mono text-sm">{mReturn != null ? `${mReturn >= 0 ? "+" : ""}${mReturn.toFixed(2)}%` : "—"}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Sharpe</div>
                <div className="font-mono text-sm">{mSharpe != null ? mSharpe.toFixed(4) : "—"}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Max DD %</div>
                <div className="font-mono text-sm">{mMaxDd != null ? mMaxDd.toFixed(2) : "—"}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Win rate %</div>
                <div className="font-mono text-sm">{mWinRate != null ? mWinRate.toFixed(1) : "—"}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Trades</div>
                <div className="font-mono text-sm">{mTrades != null ? Math.round(mTrades).toLocaleString() : "—"}</div>
              </div>
            </div>

            <div className="rounded-lg border border-border bg-background/40 p-3">
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <div className="text-sm font-medium">Equity curve</div>
                <div className="text-[11px] text-muted-foreground">
                  <code>/api/backtests/…/equity</code>
                </div>
              </div>
              <div className="h-[280px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={chartData} margin={{ left: 8, right: 8, top: 6, bottom: 0 }}>
                    <defs>
                      <linearGradient id="btEquityFill" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="var(--foreground)" stopOpacity={0.16} />
                        <stop offset="95%" stopColor="var(--foreground)" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="x" hide />
                    <YAxis
                      width={46}
                      tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                      stroke="var(--border)"
                      tickLine={false}
                      axisLine={false}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload || payload.length === 0) return null;
                        const v = payload[0]?.value as any;
                        return (
                          <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-lg">
                            <div className="text-muted-foreground">Equity</div>
                            <div className="font-mono text-foreground">
                              {typeof v === "number" && Number.isFinite(v) ? v.toFixed(2) : "—"}
                            </div>
                          </div>
                        );
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="equity"
                      stroke="var(--foreground)"
                      strokeWidth={1.5}
                      fill="url(#btEquityFill)"
                      isAnimationActive={false}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
              {equity && equity.length === 0 ? (
                <div className="mt-2 text-[11px] text-muted-foreground">No equity points returned.</div>
              ) : null}
            </div>

            <div className="rounded-lg border border-border bg-background/40 p-3">
              <div className="mb-2 flex items-baseline justify-between gap-3">
                <div className="text-sm font-medium">Recent trades</div>
                <div className="text-[11px] text-muted-foreground">
                  <code>/api/backtests/…/trades</code>
                </div>
              </div>
              {recentTrades.length === 0 ? (
                <div className="text-sm text-muted-foreground">No trades returned.</div>
              ) : (
                <div className="max-h-[320px] overflow-auto rounded-md border border-border bg-background/40">
                  <table className="w-full text-left text-[12px]">
                    <thead className="sticky top-0 bg-background/80 backdrop-blur">
                      <tr className="text-[11px] text-muted-foreground">
                        <th className="px-3 py-2">Side</th>
                        <th className="px-3 py-2">Symbol</th>
                        <th className="px-3 py-2 text-right">Qty</th>
                        <th className="px-3 py-2 text-right">Price</th>
                        <th className="px-3 py-2">Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recentTrades.map((t, idx) => {
                        const isBuy = t.side === "BUY" || t.side === "LONG";
                        const isSell = t.side === "SELL" || t.side === "SHORT";
                        const pill =
                          isBuy
                            ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100"
                            : isSell
                              ? "border-rose-500/25 bg-rose-500/10 text-rose-900 dark:text-rose-100"
                              : "border-border bg-muted/30 text-muted-foreground";
                        return (
                          <tr key={idx} className="border-t border-border">
                            <td className="px-3 py-2">
                              <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${pill}`}>
                                {t.side || "—"}
                              </span>
                            </td>
                            <td className="px-3 py-2 font-mono">{t.symbol || "—"}</td>
                            <td className="px-3 py-2 text-right font-mono">
                              {t.qty != null && Number.isFinite(t.qty) ? t.qty.toFixed(4) : "—"}
                            </td>
                            <td className="px-3 py-2 text-right font-mono">
                              {t.price != null && Number.isFinite(t.price) ? t.price.toFixed(2) : "—"}
                            </td>
                            <td className="px-3 py-2 text-muted-foreground">{fmtTs(t.ts)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

