"use client";

import { Suspense, useEffect, useMemo, useState, useRef, memo } from "react";
import { useSearchParams } from "next/navigation";
import { NexusHeaderNav } from "@/components/NexusHeaderNav";

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
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  win_rate?: number | null;
  profit_factor?: number | null;
};

type RankedRow = LeaderboardRow & { _rank: number };

function fmtNum(v: unknown, d = 2) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(d) : "—";
}
function fmtPct(v: unknown, d = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
}
function fmtInt(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? Math.round(v).toString() : "—";
}
function fmtTsRel(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  const s = Math.floor((Date.now() - ts * 1000) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}
function providerColor(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
  return (["#00d4aa","#22d3ee","#3b82f6","#8b5cf6","#f59e0b","#ef4444","#ec4899","#14b8a6"])[Math.abs(hash) % 8];
}

function TabPanelSkeleton({ label }: { label: string }) {
  return (
    <div className="flex min-h-[42vh] flex-col items-center justify-center gap-3 px-4">
      <div className="h-5 w-5 animate-spin rounded-full border-2 border-[var(--nexus-glow)] border-t-transparent" />
      <div className="text-[11px] text-[var(--nexus-muted)]">{label}</div>
    </div>
  );
}

const LeaderboardRow = memo(function LeaderboardRow({ row }: { row: RankedRow }) {
  const ret = row.total_return_pct;
  const ok = typeof ret === "number" && Number.isFinite(ret);
  const pos = ok && ret! >= 0;
  const provider = row.provider?.trim() || "Anonymous";
  const aChar = provider.charAt(0).toUpperCase();
  const aColor = providerColor(provider);
  return (
    <tr onClick={() => { window.location.href = `/leadpage/providers/${encodeURIComponent(provider)}${row.run_id ? `?run=${encodeURIComponent(row.run_id)}` : ""}`; }}
      className={`cursor-pointer border-t border-[rgba(138,149,166,0.06)] transition-colors hover:bg-[rgba(255,255,255,0.03)] ${ok ? (pos ? "bg-[rgba(0,212,170,0.02)]" : "bg-[rgba(242,92,84,0.02)]") : ""}`}>
      <td className="px-3 py-2.5 font-mono text-[rgba(226,232,240,0.6)] text-[10px]">{row._rank}</td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-lg text-[9px] font-bold"
            style={{ backgroundColor: aColor + "22", color: aColor }}>{aChar}</span>
          <div className="flex flex-col leading-tight">
            <span className="text-[12px] font-medium text-[rgba(226,232,240,0.92)] leading-none">{provider}</span>
            <span className="text-[9px] text-[var(--nexus-muted)]">{row.source ?? "—"}</span>
          </div>
        </div>
      </td>
      <td className="px-3 py-2.5 font-mono text-[rgba(226,232,240,0.75)] text-[10px]">
        <span className="max-w-[90px] inline-block truncate align-middle" title={row.run_id ?? ""}>
          {(row.run_id ?? "—").length > 10 ? (row.run_id ?? "").slice(0, 10) + "…" : (row.run_id ?? "—")}
        </span>
      </td>
      <td className="px-3 py-2.5">
        {row.ticker
          ? <span className="rounded border border-[rgba(138,149,166,0.15)] bg-[rgba(6,8,11,0.35)] px-1.5 py-0.5 text-[9px] font-mono text-[rgba(226,232,240,0.7)]">{row.ticker}</span>
          : <span className="text-[var(--nexus-muted)]">—</span>}
      </td>
      <td className={`px-3 py-2.5 text-right font-semibold tabular-nums text-[11px] ${pos ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"}`}>{fmtPct(ret, 2)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[10px] text-[rgba(226,232,240,0.75)]">{fmtNum(row.sharpe, 2)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[10px] text-[rgba(226,232,240,0.75)]">{fmtNum(row.win_rate, 1)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[10px] text-[rgba(226,232,240,0.75)]">{fmtInt(row.trade_count)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[10px] text-[rgba(242,92,84,0.8)]">{fmtNum(row.max_drawdown_pct, 1)}</td>
      <td className="px-3 py-2.5 text-right font-mono tabular-nums text-[10px] text-[rgba(226,232,240,0.75)]">{fmtNum(row.profit_factor, 2)}</td>
      <td className="px-3 py-2.5 text-right text-[10px] text-[var(--nexus-muted)]">{fmtTsRel(row.ts)}</td>
    </tr>
  );
});

export default function Leadpage() {
  const searchParams = useSearchParams();
  const focus = searchParams.get("focus") === "signals" ? "signals" : "overview";

  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"return" | "sharpe" | "mdd">("return");
  const [search, setSearch] = useState("");
  const rowsRef = useRef<LeaderboardRow[]>([]);

  /** `null` until first load on the Signals tab. */
  const [signals, setSignals] = useState<Signal[] | null>(null);

  // Leaderboard: only while Overview is active.
  useEffect(() => {
    if (focus !== "overview") return;
    let c = false;
    if (rowsRef.current.length === 0) setLoading(true);
    setError(null);
    async function load() {
      try {
        const res = await fetch(`/api/leadpage/leaderboard?limit=100&sort_by=${sortBy}`, { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (c) return;
        if (!res.ok) throw new Error(json?.error ?? `Failed (${res.status})`);
        const n = Array.isArray(json?.rows) ? json.rows : [];
        if (JSON.stringify(rowsRef.current) !== JSON.stringify(n)) {
          setRows(n);
          rowsRef.current = n;
        }
      } catch (e) {
        if (!c) setError(e instanceof Error ? e.message : "Load failed");
      } finally {
        if (!c) setLoading(false);
      }
    }
    load();
    const t = setInterval(load, 10_000);
    return () => {
      c = true;
      clearInterval(t);
    };
  }, [sortBy, focus]);

  // Signals: only while Signals tab is active.
  useEffect(() => {
    if (focus !== "signals") return;
    let cancelled = false;
    async function load() {
      try {
        const res = await fetch("/api/signals/feed?limit=50", { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (cancelled) return;
        setSignals(Array.isArray(json?.signals) ? (json.signals as Signal[]) : []);
      } catch {
        if (!cancelled) setSignals([]);
      }
    }
    void load();
    const t = setInterval(load, 15_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [focus]);

  const ranked = useMemo(() => rows.map((r, i) => ({ ...r, _rank: i + 1 })), [rows]);
  const filtered = useMemo(() => {
    if (!search.trim()) return ranked;
    const q = search.toLowerCase();
    return ranked.filter(r => (r.provider ?? "").toLowerCase().includes(q) || (r.run_id ?? "").toLowerCase().includes(q) || (r.ticker ?? "").toLowerCase().includes(q));
  }, [ranked, search]);

  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
        <div className="w-full">
          <div className="w-full flex flex-wrap items-center justify-start gap-3">
            <div className="min-w-0">
              <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">LEADERBOARD</h1>
              <p className="mt-0.5 min-h-[1.5rem] text-[10px] leading-snug tracking-wide text-[var(--nexus-muted)]">
                {focus === "signals" ? "Live provider signals" : "Ranked backtest runs"}
              </p>
            </div>
          </div>
          <div className="w-full mt-2 border-t border-[var(--nexus-rule-soft)] pt-2 flex flex-wrap items-center justify-start gap-3">
            <Suspense fallback={<div className="h-10 w-full max-w-md rounded-lg bg-[rgba(6,8,11,0.35)]" />}>
              <NexusHeaderNav active="observe" variant="section" />
            </Suspense>
          </div>
        </div>
      </header>

      <div className="nexus-bg min-h-0 flex-1 overflow-auto">
        <div className="mx-auto w-full max-w-6xl px-4 py-3 pb-10">
        {focus === "overview" ? (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div className="relative min-w-[180px] flex-1 max-w-sm">
                <svg
                  className="pointer-events-none absolute left-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-[var(--nexus-muted)]"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z" />
                </svg>
                <input
                  type="text"
                  placeholder="Search…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="nexus-input w-full rounded-lg border border-[rgba(138,149,166,0.22)] bg-[rgba(13,15,20,0.6)] py-1.5 pl-8 pr-2.5 text-[11px] text-[var(--nexus-text)] placeholder-[var(--nexus-muted)] outline-none transition-colors focus:border-[rgba(0,212,170,0.35)]"
                />
              </div>
              <div className="inline-flex rounded-lg nexus-segmented-toggle p-0.5">
                {(["return", "sharpe", "mdd"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setSortBy(k)}
                    className={`nexus-segment-btn rounded-lg px-2.5 py-1 text-[10px] transition ${sortBy === k ? "is-active" : ""}`}
                  >
                    {k === "return" ? "Return" : k === "sharpe" ? "Sharpe" : "Max DD"}
                  </button>
                ))}
              </div>
              <span className="text-[10px] text-[var(--nexus-muted)]">{loading ? "…" : `${filtered.length}`}</span>
            </div>
            {error ? (
              <div className="mb-3 rounded-lg border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-2.5 py-1.5 text-[10px] text-[rgba(242,92,84,0.95)]">
                {error}
              </div>
            ) : null}
            {loading && filtered.length === 0 && !error ? (
              <TabPanelSkeleton label="Loading results…" />
            ) : (
              <section className="overflow-hidden rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
                <div className="overflow-auto max-h-[calc(100vh-200px)]">
                  <table className="w-full min-w-[760px] border-separate border-spacing-0 text-left text-[11px]">
                    <thead className="sticky top-0 z-10 bg-[rgba(6,8,11,0.9)] backdrop-blur">
                      <tr className="text-[9px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                        <th className="px-2.5 py-2 w-8">#</th>
                        <th className="px-2.5 py-2">Provider</th>
                        <th className="px-2.5 py-2">Run</th>
                        <th className="px-2.5 py-2">Ticker</th>
                        <th className="px-2.5 py-2 text-right">Return</th>
                        <th className="px-2.5 py-2 text-right">Sharpe</th>
                        <th className="px-2.5 py-2 text-right">W Rate</th>
                        <th className="px-2.5 py-2 text-right">Trades</th>
                        <th className="px-2.5 py-2 text-right">MDD</th>
                        <th className="px-2.5 py-2 text-right">Profit</th>
                        <th className="px-2.5 py-2 text-right">When</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.length === 0 && !loading ? (
                        <tr>
                          <td className="px-3 py-8 text-center text-[var(--nexus-muted)]" colSpan={11}>
                            No results yet.
                          </td>
                        </tr>
                      ) : null}
                      {filtered.map((r) => (
                        <LeaderboardRow
                          key={`${r.source ?? "x"}:${r.provider ?? "p"}:${r.run_id ?? "norun"}`}
                          row={r}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}
          </>
        ) : (
          <>
            <div className="mb-3 flex items-center justify-between gap-2">
              <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">Signals</span>
              {signals !== null ? (
                <span className="text-[10px] text-[var(--nexus-muted)]">{signals.length} items</span>
              ) : null}
            </div>
            {signals === null ? (
              <TabPanelSkeleton label="Loading signals…" />
            ) : signals.length === 0 ? (
              <div className="rounded-lg border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.24)] p-4 text-[11px] text-[var(--nexus-muted)]">
                No signals yet.
              </div>
            ) : (
              <div className="flex flex-col gap-2 overflow-auto max-h-[calc(100vh-200px)] pr-1">
                {signals.map((s) => {
                  const kb =
                    s.kind === "ops"
                      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
                      : s.kind === "strategy"
                        ? "border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] text-[rgba(226,232,240,0.92)]"
                        : "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]";
                  return (
                    <article key={s.id} className="rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.24)] p-3">
                      <div className="mb-1 flex items-center justify-between gap-2">
                        <div className="flex items-center gap-1.5">
                          <span className={`rounded-lg border px-1.5 py-0.5 text-[8px] uppercase tracking-[0.16em] ${kb}`}>
                            {s.kind}
                          </span>
                          {s.ticker ? (
                            <span className="font-mono text-[9px] text-[var(--nexus-muted)]">{s.ticker}</span>
                          ) : null}
                        </div>
                        <span className="text-[9px] text-[var(--nexus-muted)]">{fmtTsRel(s.ts)}</span>
                      </div>
                      <div className="text-[11px] font-medium leading-tight text-[rgba(226,232,240,0.92)]">{s.title}</div>
                      {s.body ? (
                        <p className="mt-1 text-[10px] leading-relaxed text-[rgba(226,232,240,0.7)]">
                          {s.body.length > 180 ? `${s.body.slice(0, 180)}…` : s.body}
                        </p>
                      ) : null}
                      <div className="mt-1 text-[9px] text-[var(--nexus-muted)]">{s.provider}</div>
                    </article>
                  );
                })}
              </div>
            )}
          </>
        )}
        </div>
      </div>
    </div>
  );
}
