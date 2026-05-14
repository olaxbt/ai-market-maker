import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type Row = {
  source?: string;
  ts?: number | null;
  provider?: string | null;
  run_id?: string;
  title?: string | null;
  ticker?: string | null;
  trade_count?: number | null;
  total_return_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  meta?: Record<string, unknown>;
};

type RankedRow = Row & { _rank: number };

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: string;
  title: string;
  body: string;
  ticker?: string | null;
};

function fmtNum(v: unknown, digits = 2) {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function fmtTs(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  return new Date(ts * 1000).toLocaleString();
}

function fmtPct(v: unknown, digits = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(digits)}%`;
}

export default function LeaderboardProviderPage() {
  const params = useParams();
  const provider = params.provider ? decodeURIComponent(String(params.provider)) : "";
  const location = useLocation();
  const navigate = useNavigate();
  const selectedRunId = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return (qs.get("run") ?? "").trim() || null;
  }, [location.search]);

  const [leaderRows, setLeaderRows] = useState<Row[]>([]);
  const [historyRows, setHistoryRows] = useState<Row[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"return" | "sharpe" | "mdd">("return");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [lbRes, rowsRes, sigRes, folRes] = await Promise.all([
          fetch(`/api/leadpage/providers/${encodeURIComponent(provider)}/leaderboard?limit=50&sort_by=${sortBy}`, {
            cache: "no-store" as any,
          }),
          fetch(`/api/leadpage/providers/${encodeURIComponent(provider)}/rows?limit=1000`, {
            cache: "no-store" as any,
          }),
          fetch(`/api/signals/feed?limit=40&provider=${encodeURIComponent(provider)}`, {
            cache: "no-store" as any,
          }),
          fetch(`/api/social/following`, { cache: "no-store" as any }),
        ]);
        const lbJson = await lbRes.json().catch(() => ({}));
        const rowsJson = await rowsRes.json().catch(() => ({}));
        const sigJson = await sigRes.json().catch(() => ({}));
        const folJson = await folRes.json().catch(() => ({}));
        if (!lbRes.ok) throw new Error((lbJson as any)?.detail || "Failed to load leaderboard");
        if (!rowsRes.ok) throw new Error((rowsJson as any)?.detail || "Failed to load history");

        if (!cancelled) {
          setLeaderRows(Array.isArray((lbJson as any)?.rows) ? (lbJson as any).rows : []);
          setHistoryRows(Array.isArray((rowsJson as any)?.rows) ? (rowsJson as any).rows : []);
          setSignals(Array.isArray((sigJson as any)?.signals) ? (sigJson as any).signals : []);
          const provs = Array.isArray((folJson as any)?.providers) ? ((folJson as any).providers as string[]) : [];
          setFollowing(provs.includes(provider));
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load provider page");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    if (provider) void load();
    const t = window.setInterval(load, 12_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [provider, sortBy]);

  async function toggleFollow() {
    setError(null);
    try {
      const res = await fetch(`/api/social/${following ? "unfollow" : "follow"}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ provider }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Follow action failed (login required)");
      setFollowing(!following);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Follow action failed");
    }
  }

  const providerTitle = useMemo(() => {
    if (!provider) return "Provider";
    if (provider.trim().toLowerCase() === "local") return "Local backtests";
    return provider;
  }, [provider]);

  const ranked: RankedRow[] = useMemo(() => leaderRows.map((r, i) => ({ ...r, _rank: i + 1 })), [leaderRows]);

  const selectedRow = useMemo(() => {
    if (!selectedRunId) return null;
    return historyRows.find((r) => r.run_id === selectedRunId) ?? leaderRows.find((r) => r.run_id === selectedRunId) ?? null;
  }, [historyRows, leaderRows, selectedRunId]);

  const basePath = useMemo(() => `/leaderboard/providers/${encodeURIComponent(provider)}`, [provider]);
  function selectRun(runId: string | null) {
    if (!provider) return;
    if (!runId) {
      navigate(basePath);
      return;
    }
    navigate(`${basePath}?run=${encodeURIComponent(runId)}`);
  }

  const perfSeries = useMemo(() => {
    const rows = Array.isArray(historyRows) ? historyRows : [];
    const pts = rows
      .map((r) => {
        const ts = typeof r.ts === "number" && Number.isFinite(r.ts) ? r.ts : null;
        const ret = typeof r.total_return_pct === "number" && Number.isFinite(r.total_return_pct) ? r.total_return_pct : null;
        if (ts == null || ret == null) return null;
        return { ts, ret };
      })
      .filter(Boolean) as Array<{ ts: number; ret: number }>;
    pts.sort((a, b) => a.ts - b.ts);
    return pts;
  }, [historyRows]);

  const selectedPoint = useMemo(() => {
    if (!selectedRunId) return null;
    const r = selectedRow;
    if (!r) return null;
    const ts = typeof r.ts === "number" && Number.isFinite(r.ts) ? r.ts : null;
    const ret = typeof r.total_return_pct === "number" && Number.isFinite(r.total_return_pct) ? r.total_return_pct : null;
    if (ts == null || ret == null) return null;
    return { ts, ret };
  }, [selectedRunId, selectedRow]);

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Provider · {providerTitle}
              </p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">{providerTitle}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {loading ? "Loading…" : `${ranked.length} top results · ${historyRows.length} submissions · ${signals.length} signals`}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
                <Link
                  to={`/p/${encodeURIComponent(provider)}`}
                  className="rounded-lg border border-border bg-card px-3 py-2 hover:bg-muted/70"
                >
                  Public page
                </Link>
                <Link
                  to={`/leaderboard?focus=signals&provider=${encodeURIComponent(provider)}`}
                  className="rounded-lg border border-border bg-card px-3 py-2 hover:bg-muted/70"
                >
                  View signals
                </Link>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Link to="/leaderboard" className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70">
                Back
              </Link>
              <button
                type="button"
                onClick={toggleFollow}
                className="rounded-lg border border-border bg-card px-3 py-2 text-sm cursor-default hover:bg-muted/70"
                title={following ? "Unfollow this provider" : "Follow this provider"}
              >
                {following ? "Unfollow" : "Follow"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <section className="rounded-lg border border-border bg-card px-4 py-3">
            <div className="mb-2 flex items-baseline justify-between gap-3">
              <div className="text-sm font-medium">Performance (submissions)</div>
              <div className="text-[11px] text-muted-foreground">{perfSeries.length ? `${perfSeries.length} points` : "No history yet"}</div>
            </div>
            <div className="h-[160px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={perfSeries} margin={{ left: 8, right: 8, top: 6, bottom: 0 }}>
                  <defs>
                    <linearGradient id="lbRetFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--foreground)" stopOpacity={0.14} />
                      <stop offset="95%" stopColor="var(--foreground)" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="ts" hide />
                  <YAxis
                    width={44}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                    stroke="var(--border)"
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => (typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(0)}%` : "")}
                  />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload || payload.length === 0) return null;
                      const ts = (payload[0] as any)?.payload?.ts as unknown;
                      const ret = payload[0]?.value as any;
                      const when =
                        typeof ts === "number" && Number.isFinite(ts) ? new Date(ts * 1000).toLocaleString() : "—";
                      const val = typeof ret === "number" && Number.isFinite(ret) ? `${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%` : "—";
                      return (
                        <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs shadow-lg">
                          <div className="text-muted-foreground">{when}</div>
                          <div className="font-mono text-foreground">{val}</div>
                        </div>
                      );
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="ret"
                    stroke="var(--foreground)"
                    strokeWidth={1.5}
                    fill="url(#lbRetFill)"
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

        {selectedRunId && selectedRow ? (
          <section className="mt-4 rounded-lg border border-border bg-card px-4 py-3">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium">Run details</div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="rounded-md border border-border bg-muted/30 px-2 py-1 font-mono text-[11px] text-foreground/90">
                    {selectedRunId}
                  </span>
                  <span>submitted {fmtTs(selectedRow.ts)}</span>
                  {selectedRow.ticker ? <span>· {selectedRow.ticker}</span> : null}
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to={`/studio?run=${encodeURIComponent(selectedRunId)}`}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70"
                >
                  Ask in Studio
                </Link>
                <button
                  type="button"
                  onClick={() => selectRun(null)}
                  className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70"
                >
                  Clear
                </button>
              </div>
            </div>

            <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-5">
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Return %</div>
                <div className="font-mono text-sm">{fmtPct(selectedRow.total_return_pct, 2)}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Sharpe</div>
                <div className="font-mono text-sm">{fmtNum(selectedRow.sharpe, 4)}</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Max DD %</div>
                <div className="font-mono text-sm">{fmtNum(selectedRow.max_drawdown_pct, 2)}%</div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Trades</div>
                <div className="font-mono text-sm">
                  {typeof selectedRow.trade_count === "number" && Number.isFinite(selectedRow.trade_count)
                    ? Math.round(selectedRow.trade_count).toLocaleString()
                    : "—"}
                </div>
              </div>
              <div className="rounded-lg border border-border bg-background/60 px-3 py-2">
                <div className="text-[11px] text-muted-foreground">Source</div>
                <div className="font-mono text-sm">{selectedRow.source ?? "—"}</div>
              </div>
            </div>

            {selectedRow.title ? <div className="mt-2 text-sm text-muted-foreground">{selectedRow.title}</div> : null}

            {selectedPoint ? (
              <div className="mt-3 rounded-lg border border-border bg-background/40 p-3">
                <div className="mb-2 flex items-baseline justify-between gap-3">
                  <div className="text-sm font-medium">Selected point</div>
                  <div className="text-[11px] text-muted-foreground">{fmtTs(selectedPoint.ts)}</div>
                </div>
                <div className="h-[120px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={[selectedPoint]} margin={{ left: 8, right: 8, top: 6, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="ts" hide />
                      <YAxis
                        width={44}
                        tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
                        stroke="var(--border)"
                        tickLine={false}
                        axisLine={false}
                        tickFormatter={(v) => (typeof v === "number" && Number.isFinite(v) ? `${v.toFixed(0)}%` : "")}
                      />
                      <Area
                        type="monotone"
                        dataKey="ret"
                        stroke="var(--foreground)"
                        strokeWidth={1.5}
                        fill="url(#lbRetFill)"
                        isAnimationActive={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span className="text-[12px] text-muted-foreground">Sort</span>
          <div className="inline-flex rounded-xl border border-border bg-card p-1">
            {(["return", "sharpe", "mdd"] as const).map((k) => (
              <button
                key={k}
                type="button"
                onClick={() => setSortBy(k)}
                className={[
                  "rounded-lg px-3 py-1.5 text-[12px] transition",
                  sortBy === k ? "bg-muted/40" : "hover:bg-muted/30",
                ].join(" ")}
              >
                {k === "return" ? "Return %" : k === "sharpe" ? "Sharpe" : "Max DD %"}
              </button>
            ))}
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <section className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3 text-[12px] font-semibold">
              Top results
            </div>
            <div className="overflow-auto">
              <table className="w-full min-w-[520px] border-separate border-spacing-0 text-left text-[12px]">
                <thead className="sticky top-0 z-10 bg-background">
                  <tr className="text-[11px] text-muted-foreground">
                    <th className="px-3 py-3">#</th>
                    <th className="px-3 py-3">Run</th>
                    <th className="px-3 py-3">Return %</th>
                    <th className="px-3 py-3">Sharpe</th>
                    <th className="px-3 py-3">Max DD %</th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.length === 0 && !loading ? (
                    <tr>
                      <td className="px-3 py-6 text-muted-foreground" colSpan={5}>
                        No results for this provider yet.
                      </td>
                    </tr>
                  ) : null}
                  {ranked.map((r) => (
                    (() => {
                      const isSelected = !!selectedRunId && !!r.run_id && r.run_id === selectedRunId;
                      const rowCls = [
                        "border-t border-border hover:bg-muted/20 cursor-pointer",
                        isSelected ? "bg-muted/20" : "",
                      ]
                        .filter(Boolean)
                        .join(" ");
                      return (
                    <tr
                      key={`${r.run_id ?? Math.random()}:${r.ts ?? 0}`}
                      className={rowCls}
                      onClick={() => (r.run_id ? selectRun(r.run_id) : null)}
                      title={r.run_id ? "Select run" : undefined}
                    >
                      <td className="px-3 py-3">{r._rank}</td>
                      <td className="px-3 py-3">
                        <span className="line-clamp-1">{r.run_id ?? "—"}</span>
                      </td>
                      <td className="px-3 py-3 font-semibold text-[rgba(0,212,170,0.92)]">{fmtNum(r.total_return_pct, 2)}</td>
                      <td className="px-3 py-3">{fmtNum(r.sharpe, 3)}</td>
                      <td className="px-3 py-3">{fmtNum(r.max_drawdown_pct, 2)}</td>
                    </tr>
                      );
                    })()
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-border bg-card">
            <div className="border-b border-border px-4 py-3 text-[12px] font-semibold">
              Submission history (latest first)
            </div>
            <div className="max-h-[560px] overflow-auto px-4 py-3">
              {historyRows.length === 0 && !loading ? <div className="text-[12px] text-muted-foreground">No submissions yet.</div> : null}
              <div className="flex flex-col gap-2">
                {historyRows.map((r) => (
                  (() => {
                    const isSelected = !!selectedRunId && !!r.run_id && r.run_id === selectedRunId;
                    const cardCls = [
                      "rounded-xl border border-border bg-muted/20 px-3 py-2 cursor-pointer hover:bg-muted/30 transition-colors",
                      isSelected ? "ring-1 ring-ring/30 bg-muted/30" : "",
                    ]
                      .filter(Boolean)
                      .join(" ");
                    return (
                  <div
                    key={`${r.run_id ?? Math.random()}:${r.ts ?? 0}`}
                    className={cardCls}
                    onClick={() => (r.run_id ? selectRun(r.run_id) : null)}
                    title={r.run_id ? "Select run" : undefined}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-[12px]">
                        <span className="mr-2 text-muted-foreground">run</span>
                        {r.run_id ?? "—"}
                      </div>
                      <div className="text-[11px] text-muted-foreground">{fmtTs(r.ts)}</div>
                    </div>
                    <div className="mt-1 text-[11px] text-muted-foreground">
                      <span className="mr-3">
                        <span className="text-muted-foreground">ticker</span> {r.ticker ?? "—"}
                      </span>
                      <span className="mr-3">
                        <span className="text-muted-foreground">ret%</span> {fmtNum(r.total_return_pct, 2)}
                      </span>
                      <span className="mr-3">
                        <span className="text-muted-foreground">sharpe</span> {fmtNum(r.sharpe, 3)}
                      </span>
                      <span className="mr-3">
                        <span className="text-muted-foreground">mdd%</span> {fmtNum(r.max_drawdown_pct, 2)}
                      </span>
                      <span>
                        <span className="text-muted-foreground">trades</span> {typeof r.trade_count === "number" ? r.trade_count : "—"}
                      </span>
                    </div>
                    {r.title ? <div className="mt-1 text-[11px] text-muted-foreground">title {r.title}</div> : null}
                  </div>
                    );
                  })()
                ))}
              </div>
            </div>
          </section>
        </div>

        <section className="mt-3 overflow-hidden rounded-2xl border border-border bg-card">
          <div className="border-b border-border px-4 py-3 text-[12px] font-semibold">
            Signals
          </div>
          <div className="px-4 py-3">
            {signals.length === 0 && !loading ? (
              <div className="text-[12px] text-muted-foreground">
                No signals yet. See the global <Link className="underline" to="/leaderboard?focus=signals">signals</Link>.
              </div>
            ) : null}
            <div className="flex flex-col gap-2">
              {signals.map((s) => (
                <div key={s.id} className="rounded-xl border border-border bg-muted/20 px-3 py-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[12px]">
                      <span className="mr-2 rounded-lg border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.06)] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em]">
                        {s.kind}
                      </span>
                      {s.title}
                    </div>
                    <div className="text-[11px] text-muted-foreground">{fmtTs(s.ts)}</div>
                  </div>
                  <div className="mt-1 whitespace-pre-wrap break-words text-[11px] text-muted-foreground">{s.body}</div>
                </div>
              ))}
            </div>
          </div>
        </section>
        </div>
      </div>
    </div>
  );
}

