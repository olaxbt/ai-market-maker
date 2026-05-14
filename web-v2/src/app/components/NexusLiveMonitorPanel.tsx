import { useEffect, useMemo, useState } from "react";
import type * as React from "react";
import { Link, useSearchParams } from "react-router";
import { CheckCircle2, Radio } from "lucide-react";
import { LoginRequiredPanel } from "./LoginRequiredPanel";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

type Snapshot = {
  account_id: string;
  instrument: string;
  cash_usdt: number;
  realized_pnl_usdt: number;
  positions: Record<string, unknown>[];
  updated_ts: number;
};

type Trade = Record<string, unknown>;

type PortfolioHealth = {
  account_id?: string;
  ts?: number;
  mode?: string;
  balances?: Record<string, number>;
  positions?: unknown[];
  risk_caps?: Record<string, unknown>;
  error?: string;
  hint?: string;
};

function asString(v: unknown) {
  return typeof v === "string" ? v : v === null || v === undefined ? "" : String(v);
}

function fmtMoney(v: unknown) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function fmtTs(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function statusTone(status: string) {
  const s = (status || "").toUpperCase();
  if (s === "ACTIVE" || s === "RUNNING" || s === "OK") return "ok";
  if (s === "FAILED" || s === "ERROR") return "bad";
  if (s === "COMPLETED") return "done";
  return "muted";
}

function Pill({
  tone,
  children,
}: {
  tone: "ok" | "bad" | "done" | "muted";
  children: React.ReactNode;
}) {
  const cls =
    tone === "ok"
      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(0,212,170,0.92)]"
      : tone === "bad"
        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
        : tone === "done"
          ? "border-[rgba(99,102,241,0.20)] bg-[rgba(99,102,241,0.10)] text-[rgba(99,102,241,0.92)]"
          : "border-border bg-muted/20 text-muted-foreground";
  return (
    <span
      className={`inline-flex items-center rounded-lg border px-2 py-1 text-[10px] ${cls}`}
    >
      {children}
    </span>
  );
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

function totalStableUsd(balances: Record<string, number>): number {
  const stableLike = new Set(["USD", "USDT", "USDC", "DAI", "FDUSD", "TUSD"]);
  let t = 0;
  for (const [k, v] of Object.entries(balances)) {
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    if (stableLike.has(k.toUpperCase())) t += v;
  }
  return t;
}

function sortedBalances(balances: Record<string, number>) {
  return Object.entries(balances)
    .filter(([, v]) => typeof v === "number" && Number.isFinite(v) && v !== 0)
    .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
}

export default function NexusLiveMonitorPanel({
  nodes,
  edgeCount,
  tracesCount,
  wsConnected,
  payload,
}: {
  nodes: Array<Record<string, unknown>>;
  edgeCount: number;
  tracesCount: number;
  wsConnected: boolean;
  payload: Record<string, unknown> | null;
}) {
  const [searchParams] = useSearchParams();
  const runHint = (searchParams.get("run") ?? "").trim();
  const nodeHint = (searchParams.get("node") ?? "").trim();

  const [health, setHealth] = useState<PortfolioHealth | null>(null);
  const [healthErr, setHealthErr] = useState<string | null>(null);

  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [paperErr, setPaperErr] = useState<string | null>(null);
  const [paperLogin, setPaperLogin] = useState(false);
  const [loading, setLoading] = useState(true);

  /** When `?run=<run_id>` is set, hydrate replay metrics from Flow (same paths as Next `LiveMonitorPanel`). */
  const [replaySummary, setReplaySummary] = useState<Record<string, unknown> | null>(null);
  const [replayEquityLast, setReplayEquityLast] = useState<number | null>(null);
  const [replayTradeCount, setReplayTradeCount] = useState<number | null>(null);
  const [replayErr, setReplayErr] = useState<string | null>(null);
  const [replayLoading, setReplayLoading] = useState(false);

  const meta = (payload?.metadata ?? null) as Record<string, unknown> | null;
  const runId = meta && typeof meta.run_id === "string" ? meta.run_id : "—";
  const ticker = meta && typeof meta.ticker === "string" ? meta.ticker : "—";
  const status = meta && typeof meta.status === "string" ? meta.status : "—";
  const kpis = meta && typeof meta.kpis === "object" && meta.kpis ? (meta.kpis as Record<string, unknown>) : null;
  const sharpe = kpis && typeof kpis.sharpe === "number" ? kpis.sharpe : null;

  async function loadPaper() {
    try {
      const [sRes, tRes] = await Promise.all([
        fetch("/api/paper/snapshot", { cache: "no-store" as RequestCache }),
        fetch("/api/paper/trades?limit=50", { cache: "no-store" as RequestCache }),
      ]);
      const sJson = await sRes.json().catch(() => ({}));
      const tJson = await tRes.json().catch(() => ({}));
      if (sRes.status === 401 || tRes.status === 401) {
        setPaperLogin(true);
        setSnapshot(null);
        setTrades([]);
        setPaperErr(null);
        return;
      }
      setPaperLogin(false);
      if (!sRes.ok) {
        throw new Error(
          (sJson as { detail?: string })?.detail || (sJson as { error?: string })?.error || "Paper snapshot failed",
        );
      }
      if (!tRes.ok) {
        throw new Error(
          (tJson as { detail?: string })?.detail || (tJson as { error?: string })?.error || "Paper trades failed",
        );
      }
      setSnapshot(((sJson as { snapshot?: Snapshot })?.snapshot ?? null) as Snapshot | null);
      setTrades(Array.isArray((tJson as { trades?: Trade[] })?.trades) ? (tJson as { trades: Trade[] }).trades : []);
      setPaperErr(null);
    } catch (e) {
      setPaperErr(e instanceof Error ? e.message : "Paper load failed");
    }
  }

  async function loadHealth() {
    try {
      const res = await fetch("/api/pm/portfolio-health", { cache: "no-store" as RequestCache });
      const data = (await res.json().catch(() => ({}))) as PortfolioHealth;
      if (!res.ok) {
        setHealthErr(typeof data.error === "string" ? data.error : "Portfolio health failed");
        return;
      }
      setHealthErr(null);
      setHealth(data);
    } catch {
      setHealthErr("Portfolio health unreachable");
    }
  }

  useEffect(() => {
    if (!runHint) {
      setReplaySummary(null);
      setReplayEquityLast(null);
      setReplayTradeCount(null);
      setReplayErr(null);
      setReplayLoading(false);
      return;
    }

    let cancelled = false;

    async function loadReplay() {
      setReplayLoading(true);
      setReplayErr(null);
      setReplaySummary(null);
      setReplayEquityLast(null);
      setReplayTradeCount(null);
      try {
        const base = `/api/backtests/${encodeURIComponent(runHint)}`;
        const [sRes, eRes, tRes] = await Promise.all([
          fetch(`${base}/summary`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/equity?max_points=2500`, { cache: "no-store" as RequestCache }),
          fetch(`${base}/trades?limit=5000`, { cache: "no-store" as RequestCache }),
        ]);
        const sJson = (await sRes.json().catch(() => ({}))) as Record<string, unknown>;
        const eJson = (await eRes.json().catch(() => ({}))) as { points?: Array<{ equity?: number }> };
        const tJson = (await tRes.json().catch(() => ({}))) as { trades?: unknown[] };

        if (cancelled) return;
        if (!sRes.ok) {
          const msg =
            (typeof sJson.detail === "string" && sJson.detail) ||
            (typeof (sJson as { error?: string }).error === "string" && (sJson as { error: string }).error) ||
            `Summary failed (${sRes.status})`;
          throw new Error(msg);
        }
        setReplaySummary(sJson);

        const pts = Array.isArray(eJson?.points) ? eJson.points : [];
        const last = pts.length > 0 ? pts[pts.length - 1] : null;
        const eq = last && typeof last.equity === "number" && Number.isFinite(last.equity) ? last.equity : null;
        setReplayEquityLast(eq);

        const tradesArr = Array.isArray(tJson?.trades) ? tJson.trades : [];
        setReplayTradeCount(tradesArr.length);
      } catch (e) {
        if (!cancelled) {
          setReplayErr(e instanceof Error ? e.message : String(e));
        }
      } finally {
        if (!cancelled) setReplayLoading(false);
      }
    }

    void loadReplay();
    return () => {
      cancelled = true;
    };
  }, [runHint]);

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      if (cancelled) return;
      setLoading(true);
      await Promise.all([loadHealth(), loadPaper()]);
      if (!cancelled) setLoading(false);
    }
    void tick();
    const id = window.setInterval(() => void tick(), 8000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const balances = health?.balances ?? {};
  const stableTotal = useMemo(() => totalStableUsd(balances), [balances]);
  const usdt = typeof balances.USDT === "number" ? balances.USDT : null;
  const balanceRows = useMemo(() => sortedBalances(balances), [balances]);
  const positionsCount = useMemo(() => (Array.isArray(health?.positions) ? health?.positions.length : null), [health?.positions]);

  const replayMetrics = replaySummary?.metrics as Record<string, unknown> | undefined;
  const replaySharpe =
    replayMetrics && typeof replayMetrics.sharpe === "number" ? replayMetrics.sharpe : null;
  const replayReturn =
    replayMetrics && typeof replayMetrics.total_return_pct === "number"
      ? replayMetrics.total_return_pct
      : null;
  const replayMaxDd =
    replayMetrics && typeof replayMetrics.max_drawdown_pct === "number"
      ? replayMetrics.max_drawdown_pct
      : null;

  const recentTrades = useMemo(() => {
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
    return out.slice(-25).reverse();
  }, [trades]);

  const nodeSet = useMemo(() => new Set(nodes.map((n) => asString(n?.id))), [nodes]);
  const effectiveNode = nodeHint && nodeSet.has(nodeHint) ? nodeHint : "";

  const traces = useMemo(() => {
    const t = (payload as any)?.traces;
    return Array.isArray(t) ? (t as Array<Record<string, unknown>>) : [];
  }, [payload]);

  const lastTraceAge = useMemo(() => {
    if (!effectiveNode) return null;
    let lastTs = null as number | null;
    for (const t of traces) {
      if (asString((t as any)?.node_id) !== effectiveNode) continue;
      const ts = (t as any)?.timestamp;
      const tsSec = typeof ts === "number" && Number.isFinite(ts) ? ts : null;
      if (tsSec != null && (lastTs == null || tsSec > lastTs)) lastTs = tsSec;
    }
    if (lastTs == null) return null;
    return Math.max(0, Date.now() / 1000 - lastTs);
  }, [effectiveNode, traces]);

  function fmtAge(sec: number | null) {
    if (sec == null || !Number.isFinite(sec) || sec < 0) return "—";
    if (sec < 60) return `${Math.round(sec)}s`;
    if (sec < 3600) return `${Math.round(sec / 60)}m`;
    return `${(sec / 3600).toFixed(1)}h`;
  }

  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2 text-[12px]">
        <Pill tone="muted">nodes {nodes.length}</Pill>
        <Pill tone="muted">edges {edgeCount}</Pill>
        <Pill tone="muted">traces {tracesCount}</Pill>
        {wsConnected ? (
          <span className="inline-flex items-center gap-1 rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] text-[rgba(0,212,170,0.92)]">
            <Radio className="h-3 w-3" /> payload stream
          </span>
        ) : (
          <span className="text-[11px] text-muted-foreground">payload stream offline</span>
        )}
        {runHint ? (
          <Pill tone="done">
            run query <code className="font-mono">{runHint}</code>
          </Pill>
        ) : null}
        {effectiveNode ? (
          <Pill tone="done">
            node <code className="font-mono">{effectiveNode}</code> · last {fmtAge(lastTraceAge)}
          </Pill>
        ) : null}
      </div>

      {runHint ? (
        <Card className="border-[rgba(99,102,241,0.22)] bg-[rgba(99,102,241,0.04)]">
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <CardTitle className="text-[14px]">Backtest replay</CardTitle>
                <CardDescription className="text-[12px]">
                  Loaded from <code>/api/backtests/…/summary</code> + equity + trades (via <code>?run=</code>)
                </CardDescription>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  to="/control"
                  className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                >
                  Control → receipts
                </Link>
              </div>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            {replayLoading ? (
              <div className="text-[12px] text-muted-foreground">Loading replay metrics…</div>
            ) : replayErr ? (
              <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                {replayErr}
              </div>
            ) : replaySummary ? (
              <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
                <div className="space-y-2 text-[12px]">
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">run_id</span>
                    <code className="max-w-[220px] truncate text-right text-[11px]">
                      {asString(replaySummary.run_id) || runHint}
                    </code>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Sharpe</span>
                    <span className="font-mono">
                      {replaySharpe != null && Number.isFinite(replaySharpe) ? replaySharpe.toFixed(4) : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Total return %</span>
                    <span className="font-mono">
                      {replayReturn != null && Number.isFinite(replayReturn)
                        ? `${replayReturn >= 0 ? "+" : ""}${replayReturn.toFixed(2)}%`
                        : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Max DD %</span>
                    <span className="font-mono">
                      {replayMaxDd != null && Number.isFinite(replayMaxDd) ? `${replayMaxDd.toFixed(2)}%` : "—"}
                    </span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Last equity</span>
                    <span className="font-mono">{replayEquityLast != null ? fmtMoney(replayEquityLast) : "—"}</span>
                  </div>
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">Sim trades</span>
                    <span className="font-mono">{replayTradeCount != null ? String(replayTradeCount) : "—"}</span>
                  </div>
                </div>
                <details className="rounded-xl border border-border bg-muted/10 p-3">
                  <summary className="cursor-pointer select-none text-[11px] font-medium text-muted-foreground">
                    Raw replay JSON
                  </summary>
                  <pre className="mt-2 max-h-[260px] overflow-auto text-[10px] leading-relaxed">
                    {JSON.stringify(replaySummary, null, 2)}
                  </pre>
                </details>
              </div>
            ) : (
              <div className="text-[12px] text-muted-foreground">No replay data.</div>
            )}
          </CardContent>
        </Card>
      ) : null}

      <div className="grid gap-3 lg:grid-cols-3">
        <Card className="lg:col-span-1">
          <CardHeader className="border-b">
            <CardTitle className="text-[14px]">Run (from traces payload)</CardTitle>
            <CardDescription className="text-[12px]">Live metadata + KPIs</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 pt-4 text-[12px]">
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">run_id</span>
              <code className="max-w-[180px] truncate text-right text-[11px]">{runId}</code>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">ticker</span>
              <span className="font-mono">{ticker}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">status</span>
              <span>{status}</span>
            </div>
            <div className="flex justify-between gap-2">
              <span className="text-muted-foreground">Sharpe</span>
              <span className="font-mono">{sharpe != null && Number.isFinite(sharpe) ? sharpe.toFixed(3) : "—"}</span>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="border-b">
            <CardTitle className="text-[14px]">Portfolio health</CardTitle>
            <CardDescription className="text-[12px]">
              <code>/api/pm/portfolio-health</code> · {loading ? "refreshing…" : "auto 8s"}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {healthErr ? (
              <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                {healthErr}
              </div>
            ) : health ? (
              <div className="space-y-2 text-[12px]">
                {health.mode ? (
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">mode</span>
                    <span>{health.mode}</span>
                  </div>
                ) : null}
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">USDT</span>
                  <span className="font-mono tabular-nums">{fmtMoney(usdt)}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-muted-foreground">stable total</span>
                  <span className="font-mono tabular-nums">{fmtMoney(stableTotal)}</span>
                </div>
                {positionsCount != null ? (
                  <div className="flex justify-between gap-2">
                    <span className="text-muted-foreground">positions</span>
                    <span className="font-mono tabular-nums">{positionsCount}</span>
                  </div>
                ) : null}
                {health.hint ? (
                  <div className="text-[11px] text-muted-foreground">{health.hint}</div>
                ) : null}

                {balanceRows.length > 0 ? (
                  <div className="rounded-xl border border-border bg-muted/10">
                    <div className="border-b border-border px-3 py-2 text-[11px] font-medium text-muted-foreground">
                      Balances
                    </div>
                    <div className="max-h-[180px] overflow-auto p-2">
                      <table className="w-full border-separate border-spacing-0 text-left text-[11px]">
                        <thead className="sticky top-0 bg-background">
                          <tr className="text-muted-foreground">
                            <th className="px-2 py-1">Asset</th>
                            <th className="px-2 py-1 text-right">Amount</th>
                          </tr>
                        </thead>
                        <tbody>
                          {balanceRows.slice(0, 16).map(([asset, amt]) => (
                            <tr key={asset} className="border-t border-border">
                              <td className="px-2 py-1">{asset}</td>
                              <td className="px-2 py-1 text-right font-mono tabular-nums">{fmtMoney(amt)}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                ) : (
                  <div className="text-[12px] text-muted-foreground">No balances.</div>
                )}

                <details className="rounded-xl border border-border bg-muted/10 p-2">
                  <summary className="cursor-pointer select-none text-[11px] font-medium text-muted-foreground">
                    Raw health JSON
                  </summary>
                  <pre className="mt-2 max-h-[220px] overflow-auto text-[10px] leading-relaxed">
                    {JSON.stringify(health, null, 2)}
                  </pre>
                </details>
              </div>
            ) : (
              <div className="text-[12px] text-muted-foreground">No data.</div>
            )}
          </CardContent>
        </Card>

        <Card className="lg:col-span-1">
          <CardHeader className="border-b">
            <CardTitle className="text-[14px]">Topology pulse</CardTitle>
            <CardDescription className="text-[12px]">Node status snapshot</CardDescription>
          </CardHeader>
          <CardContent className="max-h-[280px] space-y-2 overflow-auto pt-4">
            {nodes
              .slice()
              .sort((a, b) => {
                const aid = asString(a?.id);
                const bid = asString(b?.id);
                if (effectiveNode && aid === effectiveNode) return -1;
                if (effectiveNode && bid === effectiveNode) return 1;
                return aid.localeCompare(bid);
              })
              .slice(0, 18)
              .map((n) => {
              const id = asString(n?.id);
              const st = asString(n?.status);
              const tone = statusTone(st);
              const selected = effectiveNode && id === effectiveNode;
              return (
                <div
                  key={id}
                  className={[
                    "flex items-center justify-between gap-3 rounded-xl border px-3 py-2",
                    selected ? "border-[rgba(0,212,170,0.28)] bg-[rgba(0,212,170,0.06)]" : "border-border bg-muted/10",
                  ].join(" ")}
                >
                  <div className="min-w-0">
                    <div className="truncate text-[12px] font-semibold">{asString(n?.label) || id}</div>
                    <div className="truncate text-[11px] text-muted-foreground">{asString(n?.actor)}</div>
                  </div>
                  <Pill tone={tone as "ok" | "bad" | "done" | "muted"}>{st || "—"}</Pill>
                </div>
              );
            })}
            {nodes.length === 0 ? (
              <div className="text-[12px] text-muted-foreground">No topology.</div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card>
          <CardHeader className="border-b">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <CardTitle className="text-[14px]">Paper trading</CardTitle>
                <CardDescription className="text-[12px]">Private per-user snapshot (requires sign-in)</CardDescription>
              </div>
              {snapshot ? (
                <span className="inline-flex items-center gap-1 text-[11px] text-[rgba(0,212,170,0.85)]">
                  <CheckCircle2 className="h-3.5 w-3.5" /> live
                </span>
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            {paperLogin ? (
              <LoginRequiredPanel body="Paper snapshot is per-user. Sign in to see balances and fills here." />
            ) : paperErr ? (
              <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                {paperErr}
              </div>
            ) : snapshot ? (
              <div className="space-y-3 text-[12px]">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-[11px] text-muted-foreground">Updated {fmtTs(snapshot.updated_ts)}</div>
                  <Link className="text-[11px] underline" to="/paper">
                    Open paper page
                  </Link>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl border border-border bg-muted/20 p-3">
                    <div className="text-[11px] text-muted-foreground">Cash (USDT)</div>
                    <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.cash_usdt)}</div>
                  </div>
                  <div className="rounded-xl border border-border bg-muted/20 p-3">
                    <div className="text-[11px] text-muted-foreground">Realized PnL</div>
                    <div className="mt-1 font-mono tabular-nums">{fmtMoney(snapshot.realized_pnl_usdt)}</div>
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold">Positions</div>
                  {asPositions(snapshot).length === 0 ? (
                    <div className="mt-1 text-muted-foreground">No open positions.</div>
                  ) : (
                    <ul className="mt-2 space-y-1">
                      {asPositions(snapshot).map((p) => (
                        <li
                          key={p.symbol}
                          className="flex justify-between gap-2 rounded-lg border border-border px-2 py-1 font-mono text-[11px]"
                        >
                          <span>{p.symbol}</span>
                          <span>
                            {p.qty} @ {p.avg_entry}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-[12px] text-muted-foreground">No paper snapshot.</div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="border-b">
            <CardTitle className="text-[14px]">Recent paper fills</CardTitle>
            <CardDescription className="text-[12px]">Last 25 (newest first)</CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            {paperLogin ? (
              <div className="text-[12px] text-muted-foreground">—</div>
            ) : recentTrades.length === 0 ? (
              <div className="text-[12px] text-muted-foreground">No fills.</div>
            ) : (
              <div className="max-h-[320px] overflow-auto">
                <table className="w-full border-separate border-spacing-0 text-left text-[11px]">
                  <thead className="sticky top-0 bg-background">
                    <tr className="text-muted-foreground">
                      <th className="px-2 py-1">Time</th>
                      <th className="px-2 py-1">Sym</th>
                      <th className="px-2 py-1">Side</th>
                      <th className="px-2 py-1">Qty</th>
                      <th className="px-2 py-1">Px</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentTrades.map((r, i) => (
                      <tr key={i} className="border-t border-border">
                        <td className="px-2 py-1 font-mono">
                          {r.ts != null ? new Date(r.ts * 1000).toLocaleTimeString() : "—"}
                        </td>
                        <td className="px-2 py-1">{r.symbol ?? "—"}</td>
                        <td className="px-2 py-1">{r.side ?? "—"}</td>
                        <td className="px-2 py-1 font-mono">{r.qty ?? "—"}</td>
                        <td className="px-2 py-1 font-mono">{r.price ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="rounded-xl border border-dashed border-border bg-muted/10 px-4 py-3 text-[11px] text-muted-foreground">
        Add <code className="text-foreground/80">?run=&lt;run_id&gt;</code> to this URL for backtest summary + last equity (see card above).
        Full Recharts history matches the Next.js <code className="text-foreground/80">LiveMonitorPanel</code>; open{" "}
        <Link className="underline" to="/control">
          Control
        </Link>{" "}
        for iteration receipts.
      </div>
    </div>
  );
}
