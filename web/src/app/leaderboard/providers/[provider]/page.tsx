"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

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
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

export default function ProviderLeadpage({ params }: { params: { provider: string } }) {
  const provider = decodeURIComponent(params.provider ?? "");
  const searchParams = useSearchParams();
  const selectedRunId = (searchParams.get("run") ?? "").trim() || null;
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
          fetch(
            `/api/leadpage/providers/${encodeURIComponent(provider)}/leaderboard?limit=50&sort_by=${sortBy}`,
            {
              cache: "no-store",
            },
          ),
          fetch(`/api/leadpage/providers/${encodeURIComponent(provider)}/rows?limit=1000`, {
            cache: "no-store",
          }),
          fetch(`/api/signals/feed?limit=40&provider=${encodeURIComponent(provider)}`, {
            cache: "no-store",
          }),
          fetch(`/api/social/following`, { cache: "no-store" }),
        ]);
        const lbJson = await lbRes.json().catch(() => ({}));
        const rowsJson = await rowsRes.json().catch(() => ({}));
        const sigJson = await sigRes.json().catch(() => ({}));
        const folJson = await folRes.json().catch(() => ({}));
        if (!lbRes.ok)
          throw new Error(
            typeof lbJson?.detail === "string" ? lbJson.detail : "Failed to load leaderboard",
          );
        if (!rowsRes.ok)
          throw new Error(
            typeof rowsJson?.detail === "string" ? rowsJson.detail : "Failed to load history",
          );

        if (!cancelled) {
          setLeaderRows(Array.isArray(lbJson?.rows) ? lbJson.rows : []);
          setHistoryRows(Array.isArray(rowsJson?.rows) ? rowsJson.rows : []);
          setSignals(Array.isArray(sigJson?.signals) ? sigJson.signals : []);
          const provs = Array.isArray(folJson?.providers) ? (folJson.providers as string[]) : [];
          setFollowing(provs.includes(provider));
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load provider page");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
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
      if (!res.ok)
        throw new Error(json?.detail || json?.error || "Follow action failed (login required)");
      setFollowing(!following);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Follow action failed");
    }
  }

  const ranked: RankedRow[] = useMemo(
    () => leaderRows.map((r, i) => ({ ...r, _rank: i + 1 })),
    [leaderRows],
  );

  const selectedRow = useMemo(() => {
    if (!selectedRunId) return null;
    return (
      historyRows.find((r) => r.run_id === selectedRunId) ??
      leaderRows.find((r) => r.run_id === selectedRunId) ??
      null
    );
  }, [historyRows, leaderRows, selectedRunId]);

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title={`PROVIDER · ${provider || "—"}`}
        subtitle="Leaderboard, submissions, and signals for this engine/trader."
        active="observe"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {selectedRunId ? (
          <section className="rounded-2xl border border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.06)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.9)]">
                Selected run
              </div>
              <Link
                href={`/leaderboard/providers/${encodeURIComponent(provider)}`}
                className="text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
              >
                clear
              </Link>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[rgba(226,232,240,0.9)]">
              <span className="rounded-lg border border-[rgba(138,149,166,0.18)] bg-[rgba(0,0,0,0.15)] px-2 py-1 font-mono">
                {selectedRunId}
              </span>
              <span className="text-[var(--nexus-muted)]">return%</span>
              <span className="font-mono tabular-nums">{fmtNum(selectedRow?.total_return_pct, 2)}</span>
              <span className="text-[var(--nexus-muted)]">sharpe</span>
              <span className="font-mono tabular-nums">{fmtNum(selectedRow?.sharpe, 3)}</span>
              <span className="text-[var(--nexus-muted)]">mdd%</span>
              <span className="font-mono tabular-nums">{fmtNum(selectedRow?.max_drawdown_pct, 2)}</span>
              <span className="text-[var(--nexus-muted)]">trades</span>
              <span className="font-mono tabular-nums">{selectedRow?.trade_count ?? "—"}</span>
              <Link
                href={`/console?view=research&run=${encodeURIComponent(selectedRunId)}`}
                className="ml-auto rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
                title="Open this run in Nexus Research"
              >
                Open in Research
              </Link>
            </div>
            {selectedRow?.title ? (
              <div className="mt-2 text-[11px] text-[rgba(226,232,240,0.85)]">{selectedRow.title}</div>
            ) : null}
          </section>
        ) : null}

        <section className="flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-[11px] text-[var(--nexus-muted)]">
              {loading
                ? "Loading…"
                : `${ranked.length} leaderboard rows · ${historyRows.length} history rows · ${signals.length} signals`}
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/leaderboard"
                className="rounded-xl border border-[rgba(138,149,166,0.25)] bg-[rgba(6,8,11,0.45)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.35)] hover:text-white"
              >
                Back
              </Link>
              <button
                type="button"
                onClick={toggleFollow}
                className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.92)] hover:border-[rgba(0,212,170,0.42)]"
              >
                {following ? "Unfollow" : "Follow"}
              </button>
              <Link
                href={`/p/${encodeURIComponent(provider)}`}
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Public
              </Link>
              <Link
                href={`/leaderboard?focus=signals&provider=${encodeURIComponent(provider)}`}
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Signals
              </Link>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-[var(--nexus-muted)]">Sort</span>
            <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
              {(["return", "sharpe", "mdd"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setSortBy(k)}
                  className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
                    sortBy === k ? "is-active" : ""
                  }`}
                >
                  {k === "return" ? "Return %" : k === "sharpe" ? "Sharpe" : "Max DD %"}
                </button>
              ))}
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
        </section>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <section className="overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
            <div className="border-b border-[rgba(138,149,166,0.14)] px-4 py-3 text-[11px] text-[rgba(226,232,240,0.9)]">
              Top results
            </div>
            <div className="overflow-auto">
              <table className="w-full min-w-[520px] border-separate border-spacing-0 text-left text-[11px]">
                <thead className="sticky top-0 z-10 bg-[rgba(6,8,11,0.9)] backdrop-blur">
                  <tr className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
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
                      <td className="px-3 py-6 text-[var(--nexus-muted)]" colSpan={5}>
                        No results for this provider yet. Publish to{" "}
                        <code>/leaderboard/providers/&lt;provider&gt;/results</code>.
                      </td>
                    </tr>
                  ) : null}
                  {ranked.map((r) => (
                    <tr
                      key={`${r.run_id ?? Math.random()}:${r.ts ?? 0}`}
                      className="border-t border-[rgba(138,149,166,0.12)] hover:bg-[rgba(255,255,255,0.02)]"
                    >
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">{r._rank}</td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.88)]">
                        <span className="nexus-line-clamp-1">{r.run_id ?? "—"}</span>
                      </td>
                      <td className="px-3 py-3 font-semibold text-[rgba(0,212,170,0.92)]">
                        {fmtNum(r.total_return_pct, 2)}
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">
                        {fmtNum(r.sharpe, 3)}
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">
                        {fmtNum(r.max_drawdown_pct, 2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
            <div className="border-b border-[rgba(138,149,166,0.14)] px-4 py-3 text-[11px] text-[rgba(226,232,240,0.9)]">
              Submission history (latest first)
            </div>
            <div className="max-h-[560px] overflow-auto px-4 py-3">
              {historyRows.length === 0 && !loading ? (
                <div className="text-[11px] text-[var(--nexus-muted)]">No submissions yet.</div>
              ) : null}
              <div className="flex flex-col gap-2">
                {historyRows.map((r) => (
                  <div
                    key={`${r.run_id ?? Math.random()}:${r.ts ?? 0}`}
                    className="rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.32)] px-3 py-2"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-[11px] text-[rgba(226,232,240,0.92)]">
                        <span className="mr-2 text-[var(--nexus-muted)]">run</span>
                        {r.run_id ?? "—"}
                      </div>
                      <div className="text-[10px] text-[var(--nexus-muted)]">{fmtTs(r.ts)}</div>
                    </div>
                    <div className="mt-1 text-[10px] text-[rgba(226,232,240,0.75)]">
                      <span className="mr-3">
                        <span className="text-[var(--nexus-muted)]">ticker</span> {r.ticker ?? "—"}
                      </span>
                      <span className="mr-3">
                        <span className="text-[var(--nexus-muted)]">ret%</span>{" "}
                        {fmtNum(r.total_return_pct, 2)}
                      </span>
                      <span className="mr-3">
                        <span className="text-[var(--nexus-muted)]">sharpe</span>{" "}
                        {fmtNum(r.sharpe, 3)}
                      </span>
                      <span className="mr-3">
                        <span className="text-[var(--nexus-muted)]">mdd%</span>{" "}
                        {fmtNum(r.max_drawdown_pct, 2)}
                      </span>
                      <span>
                        <span className="text-[var(--nexus-muted)]">trades</span>{" "}
                        {typeof r.trade_count === "number" ? r.trade_count : "—"}
                      </span>
                    </div>
                    {r.title ? (
                      <div className="mt-1 text-[10px] text-[var(--nexus-muted)]">
                        <span className="text-[rgba(226,232,240,0.7)]">title</span> {r.title}
                      </div>
                    ) : null}
                  </div>
                ))}
              </div>
            </div>
          </section>
        </div>

        <section className="mt-3 overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
          <div className="border-b border-[rgba(138,149,166,0.14)] px-4 py-3 text-[11px] text-[rgba(226,232,240,0.9)]">
            Signals
          </div>
          <div className="px-4 py-3">
            {signals.length === 0 && !loading ? (
              <div className="text-[11px] text-[var(--nexus-muted)]">
                No signals yet. See the global{" "}
                <Link className="underline text-[var(--nexus-glow)]" href="/leaderboard?focus=signals">
                  signals
                </Link>
                .
              </div>
            ) : null}
            <div className="flex flex-col gap-2">
              {signals.map((s) => (
                <div
                  key={s.id}
                  className="rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.32)] px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[11px] text-[rgba(226,232,240,0.92)]">
                      <span className="mr-2 rounded-lg border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.06)] px-2 py-0.5 text-[10px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.85)]">
                        {s.kind}
                      </span>
                      {s.title}
                    </div>
                    <div className="text-[10px] text-[var(--nexus-muted)]">{fmtTs(s.ts)}</div>
                  </div>
                  <div className="mt-1 whitespace-pre-wrap break-words text-[10px] text-[rgba(226,232,240,0.78)]">
                    {s.body}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
