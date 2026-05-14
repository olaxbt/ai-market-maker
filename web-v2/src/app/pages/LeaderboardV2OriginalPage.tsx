import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { Crown, Medal, TrendingDown, TrendingUp } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "../components/ui/tabs";

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: string;
  title: string;
  body: string;
  ticker?: string | null;
};

type LeaderboardRow = {
  source?: string;
  ts?: number | null;
  provider?: string | null;
  run_id?: string;
  ticker?: string | null;
  trade_count?: number | null;
  total_return_pct?: number | null;
  /** Excess vs buy-and-hold (percent points), when benchmark exists on the run. */
  change_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  win_rate?: number | null;
  profit_factor?: number | null;
};

type RankedRow = LeaderboardRow & { _rank: number };

/** Coerce API scalars (e.g. legacy string decimals) for display and local sort fallbacks. */
function toFiniteNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v.trim());
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

/** Align row shape with what the table expects; infer ``provider`` for disk backtests when missing. */
function normalizeLeaderboardRow(raw: Record<string, unknown>): LeaderboardRow {
  const runId = typeof raw.run_id === "string" ? raw.run_id.trim() : "";
  let provider: string | null =
    typeof raw.provider === "string" && raw.provider.trim() ? raw.provider.trim() : null;
  if (!provider) {
    if (raw.source === "local") provider = "local";
    else if (runId.startsWith("bt_")) provider = "local";
  }
  const tc = toFiniteNumber(raw.trade_count);
  const ts = toFiniteNumber(raw.ts);
  return {
    source: typeof raw.source === "string" ? raw.source : undefined,
    ts: ts !== null ? Math.round(ts) : null,
    provider,
    run_id: runId || undefined,
    ticker: typeof raw.ticker === "string" ? raw.ticker : raw.ticker === null ? null : undefined,
    trade_count: tc !== null ? Math.round(tc) : null,
    total_return_pct: toFiniteNumber(raw.total_return_pct),
    change_pct: toFiniteNumber(raw.change_pct),
    sharpe: toFiniteNumber(raw.sharpe),
    max_drawdown_pct: toFiniteNumber(raw.max_drawdown_pct),
    win_rate: toFiniteNumber(raw.win_rate),
    profit_factor: toFiniteNumber(raw.profit_factor),
  };
}

function fmtPct(v: unknown, d = 2, showSign = true) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  const sign = showSign ? (v >= 0 ? "+" : "") : "";
  return `${sign}${v.toFixed(d)}%`;
}

function fmtNum(v: unknown, d = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return v.toFixed(d);
}

function fmtInt(v: unknown) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return Math.round(v).toLocaleString();
}

function displayTraderLabel(provider: string | null | undefined) {
  const p = (provider ?? "").trim();
  if (!p) return "Anonymous";
  if (p.toLowerCase() === "local") return "Local backtests";
  return p;
}

function initials(name: string) {
  const parts = name
    .split(/[^a-zA-Z0-9]+/)
    .filter(Boolean)
    .slice(0, 2);
  const s = parts.map((p) => p[0]?.toUpperCase()).join("");
  return s || name.charAt(0).toUpperCase();
}

function getRankBadge(rank: number) {
  if (rank === 1) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-yellow-400 to-yellow-600 flex items-center justify-center">
        <Crown className="w-5 h-5 text-white" />
      </div>
    );
  }
  if (rank === 2) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-gray-300 to-gray-500 flex items-center justify-center">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  }
  if (rank === 3) {
    return (
      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-orange-400 to-orange-600 flex items-center justify-center">
        <Medal className="w-5 h-5 text-white" />
      </div>
    );
  }
  return (
    <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center text-muted-foreground font-medium">
      #{rank}
    </div>
  );
}

type RunsSurface = {
  runs_dir?: string;
  summary_json_count?: number;
  database_url_configured?: boolean;
  hint?: string;
};

export default function LeaderboardV2OriginalPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const focus = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return qs.get("focus") === "signals" ? "signals" : "overview";
  }, [location.search]);

  const providerFilter = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return (qs.get("provider") ?? "").trim();
  }, [location.search]);

  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"return" | "sharpe" | "mdd">("return");
  const rowsRef = useRef<LeaderboardRow[]>([]);
  const [signals, setSignals] = useState<Signal[] | null>(null);
  type RunsSurfaceState =
    | { kind: "idle" }
    | { kind: "loading" }
    | { kind: "ok"; data: RunsSurface }
    /** Older Flow without /leadpage/runs-surface — skip extra UI (no error). */
    | { kind: "path_hint_skipped" }
    | { kind: "error"; message: string };
  const [runsSurface, setRunsSurface] = useState<RunsSurfaceState>({ kind: "idle" });

  useEffect(() => {
    if (focus !== "overview") return;
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch(`/api/leadpage/leaderboard?limit=100&sort_by=${sortBy}`, {
          cache: "no-store" as any,
        });
        const json = await res.json().catch(() => ({}));
        if (cancelled) return;
        if (!res.ok) {
          const detail =
            typeof (json as any)?.detail === "string"
              ? (json as any).detail
              : typeof (json as any)?.error === "string"
                ? (json as any).error
                : `HTTP ${res.status}`;
          setLoadError(detail);
          setRows([]);
          rowsRef.current = [];
          return;
        }
        setLoadError(null);
        const rawRows = Array.isArray((json as any)?.rows) ? ((json as any).rows as Record<string, unknown>[]) : [];
        const next = rawRows.map((r) => normalizeLeaderboardRow(r));
        if (JSON.stringify(rowsRef.current) !== JSON.stringify(next)) {
          setRows(next);
          rowsRef.current = next;
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    const t = window.setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [focus, sortBy]);

  /** When the API returns zero rows, ask what the server sees on disk (path / summary count). */
  useEffect(() => {
    if (focus !== "overview" || loading || rows.length > 0 || loadError) {
      setRunsSurface({ kind: "idle" });
      return;
    }
    let cancelled = false;
    setRunsSurface({ kind: "loading" });
    void fetch("/api/leadpage/runs-surface", { cache: "no-store" as any })
      .then(async (res) => {
        const j = (await res.json().catch(() => ({}))) as Record<string, unknown>;
        if (cancelled) return;
        if (!res.ok) {
          const detail =
            typeof j.detail === "string"
              ? j.detail
              : typeof j.error === "string"
                ? j.error
                : `HTTP ${res.status}`;
          if (res.status === 404) {
            setRunsSurface({ kind: "path_hint_skipped" });
            return;
          }
          setRunsSurface({
            kind: "error",
            message: detail,
          });
          return;
        }
        setRunsSurface({ kind: "ok", data: j as unknown as RunsSurface });
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setRunsSurface({
            kind: "error",
            message:
              e instanceof Error
                ? e.message
                : "Network error — is Flow running at the URL in VITE_FLOW_API_BASE_URL?",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [focus, loading, rows.length, loadError]);

  useEffect(() => {
    if (focus !== "signals") return;
    let cancelled = false;
    async function load() {
      const qs = new URLSearchParams({ limit: "50" });
      if (providerFilter) qs.set("provider", providerFilter);
      const res = await fetch(`/api/signals/feed?${qs.toString()}`, { cache: "no-store" as any });
      const json = await res.json().catch(() => ({}));
      if (!cancelled) setSignals(Array.isArray((json as any)?.signals) ? (json as any).signals : []);
    }
    void load();
    const t = window.setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [focus, providerFilter]);

  const sortedRows: LeaderboardRow[] = useMemo(() => {
    const out = [...rows];
    const kReturn = (r: LeaderboardRow) =>
      typeof r.total_return_pct === "number" && Number.isFinite(r.total_return_pct)
        ? r.total_return_pct
        : Number.NEGATIVE_INFINITY;
    const kSharpe = (r: LeaderboardRow) =>
      typeof r.sharpe === "number" && Number.isFinite(r.sharpe) ? r.sharpe : Number.NEGATIVE_INFINITY;
    const kMdd = (r: LeaderboardRow) =>
      typeof r.max_drawdown_pct === "number" && Number.isFinite(r.max_drawdown_pct)
        ? r.max_drawdown_pct
        : Number.POSITIVE_INFINITY;
    if (sortBy === "sharpe") {
      out.sort((a, b) => kSharpe(b) - kSharpe(a) || kReturn(b) - kReturn(a));
    } else if (sortBy === "mdd") {
      out.sort((a, b) => kMdd(a) - kMdd(b) || kReturn(b) - kReturn(a));
    } else {
      out.sort((a, b) => kReturn(b) - kReturn(a) || kSharpe(b) - kSharpe(a));
    }
    return out;
  }, [rows, sortBy]);

  const ranked: RankedRow[] = useMemo(() => sortedRows.map((r, i) => ({ ...r, _rank: i + 1 })), [sortedRows]);
  const top3 = useMemo(() => ranked.slice(0, 3), [ranked]);
  const viteFlowApi = useMemo(
    () => ((import.meta as any).env?.VITE_FLOW_API_BASE_URL as string | undefined)?.trim() || "http://127.0.0.1:8001",
    [],
  );
  const podium = useMemo(() => {
    const first = top3.find((r) => r._rank === 1);
    const second = top3.find((r) => r._rank === 2);
    const third = top3.find((r) => r._rank === 3);
    // Visual podium order: 2nd, 1st, 3rd (center winner).
    return [second, first, third].filter(Boolean) as RankedRow[];
  }, [top3]);

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Leaderboard</p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">Trader leaderboard</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {focus === "signals"
                  ? "Live provider signals"
                  : "Ranked runs from this Flow API (local backtests under .runs, optional Postgres, published externals)."}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Tabs value={focus} onValueChange={(v) => navigate(`/leaderboard?focus=${v}`)}>
                <TabsList>
                  <TabsTrigger value="overview">Results</TabsTrigger>
                  <TabsTrigger value="signals">Signals</TabsTrigger>
                </TabsList>
              </Tabs>
              <select
                className="px-1 py-2 bg-input-background border border-border rounded-lg text-sm"
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                disabled={focus !== "overview"}
              >
                <option value="return">Sort: Return</option>
                <option value="sharpe">Sort: Sharpe</option>
                <option value="mdd">Sort: Max DD</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl space-y-6">
          {loadError ? (
            <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              <p className="font-medium">Could not load leaderboard</p>
              <p className="mt-1 text-destructive/90">{loadError}</p>
              <p className="mt-2 text-xs text-muted-foreground">
                Confirm the Flow API is running (Vite proxies to{" "}
                <code className="rounded bg-muted px-1 py-0.5">VITE_FLOW_API_BASE_URL</code>). If the API is in
                Docker, mount the repo&apos;s <code className="rounded bg-muted px-1 py-0.5">.runs</code> or set{" "}
                <code className="rounded bg-muted px-1 py-0.5">AIMM_RUNS_DIR</code>. Debug:{" "}
                <code className="rounded bg-muted px-1 py-0.5">GET /leadpage/runs-surface</code>
              </p>
            </div>
          ) : null}
          {focus === "overview" ? (
            <>
              {top3.length > 0 ? (
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8 items-end">
                {podium.map((r) => {
                  const providerId = (r.provider ?? "").trim() || "local";
                  const displayName = displayTraderLabel(providerId);
                  const ret = r.total_return_pct;
                  const to = `/leaderboard/providers/${encodeURIComponent(providerId)}`;
                  const height =
                    r._rank === 1
                      ? "sm:min-h-[320px]"
                      : r._rank === 2
                        ? "sm:min-h-[290px]"
                        : "sm:min-h-[270px]";
                  return (
                    <Link
                      key={`${providerId}:${r._rank}`}
                      to={to}
                      className={`bg-card rounded-lg border-2 p-6 text-center cursor-pointer flex flex-col justify-end ${height} transition-colors hover:bg-muted/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40 ${
                        r._rank === 1
                          ? "border-yellow-500"
                          : r._rank === 2
                            ? "border-gray-400"
                            : "border-orange-500"
                      }`}
                    >
                      <div className="flex justify-center mb-3">{getRankBadge(r._rank)}</div>
                      <div className="w-16 h-16 rounded-full bg-primary text-primary-foreground flex items-center justify-center mx-auto mb-3 text-xl">
                        {initials(displayName)}
                      </div>
                      <h3 className="mb-1">{displayName}</h3>
                      <div className={`text-2xl mb-1 ${typeof ret === "number" && ret >= 0 ? "text-green-500" : "text-red-500"}`}>
                        {fmtPct(ret, 2)}
                      </div>
                      <div className="text-sm text-muted-foreground">
                        Sharpe {fmtNum(r.sharpe, 2)} · Trades {fmtInt(r.trade_count)}
                      </div>
                    </Link>
                  );
                })}
              </div>
            ) : null}

            <div className="bg-card rounded-lg border border-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-muted/50 border-b border-border">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs text-muted-foreground uppercase tracking-wider">
                        Rank
                      </th>
                      <th className="px-6 py-3 text-left text-xs text-muted-foreground uppercase tracking-wider">
                        Trader
                      </th>
                      <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                        Total Return
                      </th>
                      <th
                        className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider"
                        title="Excess return vs buy-and-hold benchmark when the run includes a benchmark block."
                      >
                        Change
                      </th>
                      <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                        Win Rate
                      </th>
                      <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                        Trades
                      </th>
                      <th
                        className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider"
                        title="Peak-to-trough drawdown as a positive percentage of capital (engine convention)."
                      >
                        Max DD
                      </th>
                      <th className="px-6 py-3 text-right text-xs text-muted-foreground uppercase tracking-wider">
                        Sharpe
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {!loading && ranked.length === 0 ? (
                      <tr>
                        <td className="px-6 py-10 text-center text-muted-foreground" colSpan={8}>
                          <p className="font-medium text-foreground">No results yet.</p>
                          <p className="mt-2 max-w-xl mx-auto text-sm">
                            The page loaded, but the Flow API returned zero rows. Vite proxies{" "}
                            <code className="rounded bg-muted px-1 py-0.5 text-xs">/api/*</code> to{" "}
                            <code className="rounded bg-muted px-1 py-0.5 text-xs">{viteFlowApi}</code> (set{" "}
                            <code className="rounded bg-muted px-1 py-0.5 text-xs">VITE_FLOW_API_BASE_URL</code> in{" "}
                            <code className="rounded bg-muted px-1 py-0.5 text-xs">web-v2/.env</code>).
                          </p>
                          {runsSurface.kind === "ok" ? (
                            <div className="mt-4 rounded-lg border border-border bg-muted/30 px-4 py-3 text-left text-xs font-mono text-foreground/90 space-y-1 max-w-2xl mx-auto">
                              <div>
                                <span className="text-muted-foreground">API runs_dir:</span>{" "}
                                {runsSurface.data.runs_dir ?? "—"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">summary.json trees:</span>{" "}
                                {runsSurface.data.summary_json_count ?? "—"}
                              </div>
                              <div>
                                <span className="text-muted-foreground">Postgres leaderboard DB:</span>{" "}
                                {runsSurface.data.database_url_configured ? "configured" : "not used"}
                              </div>
                              {runsSurface.data.summary_json_count === 0 ? (
                                <p className="mt-2 text-[11px] text-muted-foreground font-sans normal-case">
                                  If you ran backtests on this machine but the count is 0, the API process is reading a
                                  different <code className="rounded bg-muted px-1">.runs</code> than your repo (common
                                  with Docker). Run Flow from the repo root, set{" "}
                                  <code className="rounded bg-muted px-1">AIMM_RUNS_DIR</code> on the API, or ensure{" "}
                                  <code className="rounded bg-muted px-1">docker-compose.prod.yml</code> bind-mounts{" "}
                                  <code className="rounded bg-muted px-1">./.runs</code> (default in this repo).
                                </p>
                              ) : (
                                <p className="mt-2 text-[11px] text-muted-foreground font-sans normal-case">
                                  The API sees summaries on disk but returned no leaderboard rows — try restarting the
                                  Flow API after upgrading, or check Postgres rows if{" "}
                                  <code className="rounded bg-muted px-1">DATABASE_URL</code> is set.
                                </p>
                              )}
                            </div>
                          ) : runsSurface.kind === "error" ? (
                            <div className="mt-4 rounded-lg border border-border bg-muted/25 px-4 py-3 text-left text-xs text-muted-foreground max-w-2xl mx-auto">
                              <p className="font-medium text-foreground/90">Optional path check failed</p>
                              <p className="mt-1 font-mono text-[11px]">{runsSurface.message}</p>
                            </div>
                          ) : runsSurface.kind === "loading" ? (
                            <p className="mt-3 text-xs text-muted-foreground">Checking where the API reads `.runs`…</p>
                          ) : null}
                        </td>
                      </tr>
                    ) : null}
                    {ranked.map((r) => {
                      const providerId = (r.provider ?? "").trim() || "local";
                      const displayName = displayTraderLabel(providerId);
                      const to = `/leaderboard/providers/${encodeURIComponent(providerId)}`;
                      const ret = typeof r.total_return_pct === "number" ? r.total_return_pct : null;
                      const ch = r.change_pct;
                      const okCh = typeof ch === "number" && Number.isFinite(ch);
                      const deltaPos = okCh && ch! >= 0;
                      return (
                        <tr
                          key={`${providerId}:${r._rank}:${r.run_id ?? ""}`}
                          className="hover:bg-muted/30 transition-colors cursor-pointer focus-within:bg-muted/30"
                          role="button"
                          tabIndex={0}
                          onClick={() => navigate(to)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              navigate(to);
                            }
                          }}
                          title="Open provider details"
                        >
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-3">{getRankBadge(r._rank)}</div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                                {initials(displayName)}
                              </div>
                              <div className="min-w-0">
                                <div className="font-medium truncate max-w-[260px]">{displayName}</div>
                                <div className="text-xs text-muted-foreground truncate max-w-[260px]">
                                  {r.run_id ?? "—"}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <span className={`${ret !== null && ret >= 0 ? "text-green-500" : "text-red-500"} font-medium`}>
                              {fmtPct(r.total_return_pct, 2)}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            {okCh ? (
                              <div className={`flex items-center justify-end gap-1 ${deltaPos ? "text-green-500" : "text-red-500"}`}>
                                {deltaPos ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                                <span>{fmtPct(ch, 2, false)}</span>
                              </div>
                            ) : (
                              <span className="text-muted-foreground">—</span>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <span>{fmtPct(r.win_rate, 1, false)}</span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <span>{fmtInt(r.trade_count)}</span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <span>{typeof r.max_drawdown_pct === "number" ? `${r.max_drawdown_pct.toFixed(2)}%` : "—"}</span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right">
                            <span>{fmtNum(r.sharpe, 2)}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        ) : (
          <div className="bg-card rounded-lg border border-border overflow-hidden">
            <div className="p-4 border-b border-border">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-sm text-muted-foreground">
                  {providerFilter ? (
                    <>
                      Filtering provider <span className="font-mono text-foreground/90">{providerFilter}</span>
                    </>
                  ) : (
                    "Global feed"
                  )}
                </div>
              </div>
            </div>
            <div className="p-4 space-y-3">
              {signals === null ? (
                <div className="text-sm text-muted-foreground">Loading signals…</div>
              ) : signals.length === 0 ? (
                <div className="text-sm text-muted-foreground">No signals yet.</div>
              ) : (
                signals.map((s) => (
                  <div key={s.id} className="rounded-xl border border-border bg-muted/20 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-sm font-medium">{s.title}</div>
                      <div className="text-xs text-muted-foreground">{new Date(s.ts * 1000).toLocaleString()}</div>
                    </div>
                    {s.body ? (
                      <div className="mt-1 text-sm text-muted-foreground whitespace-pre-wrap">{s.body}</div>
                    ) : null}
                    <div className="mt-2 text-xs text-muted-foreground">{s.provider}</div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
    </div>
  );
}

