import { useEffect, useMemo, useState } from "react";
import { Area, AreaChart, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { Progress } from "./ui/progress";

type BacktestJob =
  | { status: "queued" | "running"; step?: number; total_steps?: number; trade_count?: number; equity?: number | null; capital?: number | null; positions?: number; ts?: number | null }
  | { status: "completed"; result?: { run_id?: string } }
  | { status: "failed"; error?: string };

type BacktestSummary = {
  run_id?: string;
  metrics?: Record<string, unknown>;
  start_ts?: number | null;
  end_ts?: number | null;
  start_iso?: string | null;
  end_iso?: string | null;
};

type EquityPoint = { ts?: number; t?: number; equity?: number; value?: number };

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

function toMs(x: number): number {
  // Heuristic: ms timestamps are ~1e12+, seconds are ~1e9+
  return x > 10_000_000_000 ? x : x * 1000;
}

export function BacktestInlineWidget({ runId }: { runId: string }) {
  const rid = (runId || "").trim();
  const [job, setJob] = useState<BacktestJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [doneRunId, setDoneRunId] = useState<string | null>(null);
  const [summary, setSummary] = useState<BacktestSummary | null>(null);
  const [equity, setEquity] = useState<EquityPoint[] | null>(null);
  const [trades, setTrades] = useState<TradeRow[] | null>(null);

  const pct = useMemo(() => {
    const total = (job as any)?.total_steps;
    const step = (job as any)?.step;
    if (!total || !step) return 0;
    return Math.max(0, Math.min(100, (step / total) * 100));
  }, [job]);

  const compactStats = useMemo(() => {
    const status = (job as any)?.status as string | undefined;
    const tradeCount = typeof (job as any)?.trade_count === "number" ? (job as any).trade_count : 0;
    const equity = typeof (job as any)?.equity === "number" ? (job as any).equity : null;
    const capital = typeof (job as any)?.capital === "number" ? (job as any).capital : null;
    // NOTE: Do not derive "return" from (equity-capital)/capital — `capital` is free collateral only,
    // not initial equity, so that ratio swings wildly (0% ↔ 100%+) during leveraged runs.
    return { status, tradeCount, equity, capital };
  }, [job]);

  useEffect(() => {
    setError(null);
    setJob(null);
    setDoneRunId(null);
    setSummary(null);
    setEquity(null);
    setTrades(null);
    let cancelled = false;
    let t: any = null;
    let es: EventSource | null = null;

    function handleTerminal(j: any) {
      if (j?.status === "completed") {
        const r = j?.result?.run_id;
        setDoneRunId(typeof r === "string" && r.trim() ? r.trim() : rid);
        return true;
      }
      if (j?.status === "failed") {
        setError(j?.error || "Backtest failed");
        return true;
      }
      return false;
    }

    async function poll(intervalMs: number) {
      if (!rid) return;
      try {
        const res = await fetch(`/api/backtests/jobs/${encodeURIComponent(rid)}`, { cache: "no-store" as any });
        const json = (await res.json().catch(() => ({}))) as BacktestJob;
        if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || `Poll failed (${res.status})`);
        if (cancelled) return;
        setJob(json);
        if (handleTerminal(json as any)) return;
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Backtest poll failed");
        return;
      }
      t = setTimeout(() => void poll(intervalMs), intervalMs);
    }

    // Prefer SSE for large fanout; fall back to polling if unavailable.
    try {
      es = new EventSource(`/api/backtests/jobs/${encodeURIComponent(rid)}/stream`);
      es.onmessage = (evt) => {
        if (cancelled) return;
        try {
          const j = JSON.parse(evt.data || "{}");
          setJob(j);
          if (handleTerminal(j)) {
            try {
              es?.close();
            } catch {}
          }
        } catch (e: any) {
          setError(e?.message || "Backtest stream parse failed");
        }
      };
      es.addEventListener("error", () => {
        if (cancelled) return;
        try {
          es?.close();
        } catch {}
        es = null;
        // Conservative polling fallback to avoid hammering the server.
        void poll(1500);
      });
    } catch {
      void poll(1500);
    }

    return () => {
      cancelled = true;
      if (t) clearTimeout(t);
      if (es) {
        try {
          es.close();
        } catch {}
      }
    };
  }, [rid]);

  useEffect(() => {
    let cancelled = false;
    async function loadResults(r: string) {
      try {
        const base = `/api/backtests/${encodeURIComponent(r)}`;
        const [sRes, eRes, tRes] = await Promise.all([
          fetch(`${base}/summary`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/equity?max_points=140`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/trades?limit=12`, { cache: "no-store" as RequestCache }),
        ]);
        const sJson = (await sRes.json().catch(() => ({}))) as BacktestSummary;
        const eJson = (await eRes.json().catch(() => ({}))) as { points?: EquityPoint[] };
        const tJson = (await tRes.json().catch(() => ({}))) as { trades?: TradeRow[] };
        if (!sRes.ok) throw new Error((sJson as any)?.detail || (sJson as any)?.error || `Failed to load summary (${sRes.status})`);
        if (cancelled) return;
        setSummary(sJson);
        setEquity(Array.isArray(eJson?.points) ? eJson.points : []);
        setTrades(Array.isArray(tJson?.trades) ? tJson.trades : []);
      } catch (e: any) {
        if (!cancelled) setError(e?.message || "Failed to load results");
      }
    }
    if (doneRunId) void loadResults(doneRunId);
    return () => {
      cancelled = true;
    };
  }, [doneRunId]);

  const metrics = (summary?.metrics ?? {}) as Record<string, unknown>;
  /** Total return vs initial cash — only from completed `summary.json` (not live job snapshots). */
  const mReturn = asNum(metrics?.total_return_pct);
  const mMaxDd = asNum(metrics?.max_drawdown_pct);
  const mSharpe = asNum(metrics?.sharpe) ?? asNum(metrics?.sharpe_ratio);
  const mTrades = asNum(metrics?.trade_count) ?? asNum(metrics?.total_trades) ?? compactStats.tradeCount;

  const retColor =
    mReturn == null
      ? "text-muted-foreground"
      : mReturn >= 0
        ? "text-emerald-600 dark:text-emerald-400"
        : "text-rose-600 dark:text-rose-400";

  const spark = useMemo(() => {
    const pts = equity ?? [];
    return pts.map((p, idx) => ({
      x: typeof p.ts === "number" ? toMs(p.ts) : typeof p.t === "number" ? toMs(p.t) : idx,
      y: typeof p.equity === "number" ? p.equity : typeof p.value === "number" ? p.value : null,
    }));
  }, [equity]);

  const recentTrades = useMemo(() => {
    const rows = Array.isArray(trades) ? trades : [];
    const norm = rows
      .map((t) => {
        const tsRaw = typeof t.ts === "number" ? t.ts : typeof t.created_ts === "number" ? t.created_ts : null;
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
        return { tsMs: typeof tsRaw === "number" ? toMs(tsRaw) : null, symbol, side, qty, price };
      })
      .filter((t) => t.symbol || t.side || t.qty != null || t.price != null);
    return norm.slice(-6).reverse();
  }, [trades]);

  const sparkStats = useMemo(() => {
    const ys = spark.map((p) => p.y).filter((y): y is number => typeof y === "number" && Number.isFinite(y));
    if (ys.length === 0) return null;
    const start = ys[0];
    const end = ys[ys.length - 1];
    const min = Math.min(...ys);
    const max = Math.max(...ys);
    return { start, end, min, max };
  }, [spark]);

  const tradeMarkers = useMemo(() => {
    if (!doneRunId) return [];
    const pts = spark.filter((p) => typeof p.y === "number" && Number.isFinite(p.y)) as Array<{ x: number; y: number }>;
    if (pts.length === 0) return [];
    const marks = recentTrades
      .filter((t: any) => typeof t.tsMs === "number" && Number.isFinite(t.tsMs))
      .map((t: any) => {
        const tx = t.tsMs as number;
        let best = pts[0];
        let bestD = Math.abs(best.x - tx);
        for (let i = 1; i < pts.length; i++) {
          const d = Math.abs(pts[i].x - tx);
          if (d < bestD) {
            bestD = d;
            best = pts[i];
          }
        }
        return { x: best.x, y: best.y, side: t.side };
      });
    return marks;
  }, [doneRunId, spark, recentTrades]);

  const timeRange = useMemo(() => {
    const sIso = (summary as any)?.start_iso;
    const eIso = (summary as any)?.end_iso;
    if (typeof sIso === "string" && typeof eIso === "string" && sIso && eIso) return { s: sIso, e: eIso };
    const sTs = (summary as any)?.start_ts;
    const eTs = (summary as any)?.end_ts;
    if (typeof sTs === "number" && typeof eTs === "number") return { s: new Date(sTs).toISOString(), e: new Date(eTs).toISOString() };
    return null;
  }, [summary]);

  return (
    <div className="rounded-2xl border border-border/60 bg-gradient-to-b from-card/70 to-card/30 px-4 py-3 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <div className="text-sm font-semibold font-mono tracking-tight">BACKTEST</div>
            {doneRunId ? (
              <span className="rounded-full bg-muted/50 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                done
              </span>
            ) : null}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">
            run <code className="font-mono">{rid}</code>
          </div>
          {doneRunId && timeRange ? (
            <div className="mt-1 text-[10px] text-muted-foreground font-mono">
              {timeRange.s.replace("T", " ").replace("Z", "Z")} → {timeRange.e.replace("T", " ").replace("Z", "Z")}
            </div>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          {doneRunId ? (
            <a
              href={`/backtests#run-${encodeURIComponent(doneRunId)}`}
              className="text-[11px] font-medium text-muted-foreground hover:text-foreground transition-colors font-mono"
            >
              Open full report
            </a>
          ) : null}
        </div>
      </div>

      {error ? (
        <div className="mt-3 rounded-md border border-destructive/35 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-xl border border-border/50 bg-background/30 px-3 py-2">
              <div className="text-[11px] text-muted-foreground">Return</div>
              <div className={`font-mono text-xs ${retColor}`}>
                {mReturn == null ? "—" : `${mReturn >= 0 ? "+" : ""}${mReturn.toFixed(2)}%`}
              </div>
            </div>
            <div className="rounded-xl border border-border/50 bg-background/30 px-3 py-2">
              <div className="text-[11px] text-muted-foreground">Max DD</div>
              <div className="font-mono text-xs text-foreground">{mMaxDd == null ? "—" : `${mMaxDd.toFixed(2)}%`}</div>
            </div>
            <div className="rounded-xl border border-border/50 bg-background/30 px-3 py-2">
              <div className="text-[11px] text-muted-foreground">Sharpe</div>
              <div className="font-mono text-xs text-foreground">{mSharpe == null ? "—" : mSharpe.toFixed(2)}</div>
            </div>
            <div className="rounded-xl border border-border/50 bg-background/30 px-3 py-2">
              <div className="text-[11px] text-muted-foreground">Trades</div>
              <div className="font-mono text-xs text-foreground">
                {typeof mTrades === "number" ? Math.round(mTrades).toLocaleString() : compactStats.tradeCount.toLocaleString()}
              </div>
            </div>
          </div>

          {doneRunId ? (
            <div className="grid gap-2 sm:grid-cols-3">
              <div className="sm:col-span-2 rounded-xl border border-border/50 bg-background/25 px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] text-muted-foreground">Equity</div>
                  <div className="font-mono text-[11px] text-muted-foreground">
                    {compactStats.equity == null ? "—" : compactStats.equity.toFixed(2)}
                  </div>
                </div>
                <div className="mt-2 h-[78px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={spark}>
                      <XAxis dataKey="x" hide />
                      <YAxis dataKey="y" hide domain={["dataMin", "dataMax"]} />
                      <Tooltip
                        cursor={false}
                        content={({ active, payload }) => {
                          if (!active || !payload || payload.length === 0) return null;
                          const v = payload[0]?.value as any;
                          return (
                            <div className="rounded-md border border-border bg-popover px-2.5 py-2 text-[11px] shadow-lg">
                              <div className="text-muted-foreground">Equity</div>
                              <div className={`font-mono ${retColor}`}>
                                {typeof v === "number" && Number.isFinite(v) ? v.toFixed(2) : "—"}
                              </div>
                            </div>
                          );
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="y"
                        stroke="currentColor"
                        strokeWidth={1.5}
                        className={retColor}
                        fill="currentColor"
                        fillOpacity={0.10}
                        isAnimationActive={false}
                      />
                      {tradeMarkers.length ? (
                        <Scatter
                          data={tradeMarkers}
                          dataKey="y"
                          fill="currentColor"
                          shape={(props: any) => {
                            const { cx, cy, payload } = props || {};
                            const side = (payload?.side || "").toString().toUpperCase();
                            const isBuy = side === "BUY" || side === "LONG";
                            const isSell = side === "SELL" || side === "SHORT";
                            const cls = isBuy ? "fill-emerald-500" : isSell ? "fill-rose-500" : "fill-muted-foreground";
                            return <circle cx={cx} cy={cy} r={2.5} className={cls} />;
                          }}
                          isAnimationActive={false}
                        />
                      ) : null}
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
                {sparkStats ? (
                  <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
                    <span className="font-mono">
                      start {sparkStats.start.toFixed(0)} → end {sparkStats.end.toFixed(0)}
                    </span>
                    <span className="font-mono">
                      min {sparkStats.min.toFixed(0)} / max {sparkStats.max.toFixed(0)}
                    </span>
                  </div>
                ) : null}
              </div>
              <div className="rounded-xl border border-border/50 bg-background/25 px-3 py-2">
                <div className="flex items-center justify-between">
                  <div className="text-[11px] text-muted-foreground">Recent trades</div>
                  <div className="text-[10px] text-muted-foreground font-mono">{recentTrades.length ? `${recentTrades.length} shown` : ""}</div>
                </div>
                {recentTrades.length === 0 ? (
                  <div className="mt-2 text-xs text-muted-foreground">No trades.</div>
                ) : (
                  <div className="mt-2 max-h-[108px] overflow-auto pr-1 space-y-1">
                    {recentTrades.map((t, idx) => {
                      const isBuy = t.side === "BUY" || t.side === "LONG";
                      const isSell = t.side === "SELL" || t.side === "SHORT";
                      const pill = isBuy ? "text-emerald-600 dark:text-emerald-400" : isSell ? "text-rose-600 dark:text-rose-400" : "text-muted-foreground";
                      return (
                        <div key={idx} className="flex items-center justify-between gap-2 text-[11px] border-b border-border/40 last:border-b-0 pb-1 last:pb-0">
                          <div className="min-w-0">
                            <span className={`font-mono ${pill}`}>{t.side || "—"}</span>{" "}
                            <span className="text-muted-foreground">{t.symbol || ""}</span>
                          </div>
                          <div className="shrink-0 font-mono text-muted-foreground">
                            {t.qty == null ? "—" : t.qty.toFixed(4)} @ {t.price == null ? "—" : t.price.toFixed(2)}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="space-y-2">
              <Progress value={pct} />
              <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{compactStats.status || "running"}</span>
                <span className="font-mono">
                  {job && (job as any).step ? (job as any).step : 0}
                  {job && (job as any).total_steps ? ` / ${(job as any).total_steps}` : ""}
                </span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

