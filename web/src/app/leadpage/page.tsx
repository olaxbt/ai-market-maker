"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: "strategy" | "ops" | "discussion" | string;
  title: string;
  body: string;
  ticker?: string | null;
  result_provider?: string | null;
  result_run_id?: string | null;
};

type LeaderboardRow = {
  source?: "local" | "external" | string;
  ts?: number | null;
  provider?: string | null;
  run_id?: string;
  title?: string | null;
  ticker?: string | null;
  steps?: number | null;
  trade_count?: number | null;
  total_return_pct?: number | null;
  sharpe?: number | null;
  max_drawdown_pct?: number | null;
  win_rate?: number | null;
  profit_factor?: number | null;
  meta?: Record<string, unknown> | null;
};

type RankedLeaderboardRow = LeaderboardRow & { _rank: number };

function fmtNum(v: unknown, digits = 2) {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toFixed(digits);
}

function fmtPct(v: unknown, digits = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(digits)}`;
}

function localScanStatus(meta: unknown): string | null {
  if (!meta || typeof meta !== "object") return null;
  const m = meta as Record<string, unknown>;
  if (m.kind !== "local_scan") return null;
  return typeof m.execution_status === "string" ? m.execution_status : null;
}

function fmtInt(v: unknown) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return Math.round(v).toString();
}

function fmtTs(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

export default function Leadpage() {
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [providers, setProviders] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortBy, setSortBy] = useState<"return" | "sharpe" | "mdd">("return");
  const [providerFilter, setProviderFilter] = useState<string>("");

  const [signals, setSignals] = useState<Signal[]>([]);
  const [signalsLoading, setSignalsLoading] = useState(true);
  const [signalsError, setSignalsError] = useState<string | null>(null);
  const [signalsKind, setSignalsKind] = useState<"all" | "strategy" | "ops" | "discussion">("all");
  const [focus, setFocus] = useState<"overview" | "signals">("overview");

  useEffect(() => {
    function syncFromLocation() {
      if (typeof window === "undefined") return;
      const qs = new URLSearchParams(window.location.search);
      const f = (qs.get("focus") ?? "").trim();
      setFocus(f === "signals" ? "signals" : "overview");
      const p = (qs.get("provider") ?? "").trim();
      setProviderFilter(p);
    }

    const _pushState = history.pushState;
    const _replaceState = history.replaceState;
    history.pushState = function (...args) {
      const r = _pushState.apply(history, args as unknown as [unknown, string, string?]) as unknown;
      window.dispatchEvent(new Event("aimm:locationchange"));
      return r;
    } as typeof history.pushState;
    history.replaceState = function (...args) {
      const r = _replaceState.apply(history, args as unknown as [unknown, string, string?]) as unknown;
      window.dispatchEvent(new Event("aimm:locationchange"));
      return r;
    } as typeof history.replaceState;

    syncFromLocation();
    window.addEventListener("popstate", syncFromLocation);
    window.addEventListener("aimm:locationchange", syncFromLocation);
    return () => {
      history.pushState = _pushState;
      history.replaceState = _replaceState;
      window.removeEventListener("popstate", syncFromLocation);
      window.removeEventListener("aimm:locationchange", syncFromLocation);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const pRes = await fetch("/api/leadpage/providers", { cache: "no-store" });
        const pJson = await pRes.json().catch(() => ({}));
        if (!cancelled) {
          setProviders(Array.isArray(pJson?.providers) ? pJson.providers : []);
        }

        const res = await fetch(`/api/leadpage/leaderboard?limit=100&sort_by=${sortBy}`, {
          cache: "no-store",
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
          const msg =
            typeof json?.error === "string" ? json.error : `Request failed (${res.status})`;
          throw new Error(msg);
        }
        if (!cancelled) {
          setRows(Array.isArray(json?.rows) ? json.rows : []);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load leaderboard");
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
  }, [sortBy]);

  useEffect(() => {
    let cancelled = false;
    async function loadSignals() {
      setSignalsLoading(true);
      setSignalsError(null);
      try {
        const qs = new URLSearchParams({ limit: "80" });
        if (providerFilter.trim()) qs.set("provider", providerFilter.trim());
        const res = await fetch(`/api/signals/feed?${qs.toString()}`, { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(json?.detail || json?.error || "Failed to load signals");
        if (!cancelled) setSignals(Array.isArray(json?.signals) ? (json.signals as Signal[]) : []);
      } catch (e) {
        if (!cancelled) setSignalsError(e instanceof Error ? e.message : "Failed to load signals");
      } finally {
        if (!cancelled) setSignalsLoading(false);
      }
    }
    void loadSignals();
    const t = window.setInterval(loadSignals, 10_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [providerFilter]);

  const ranked: RankedLeaderboardRow[] = useMemo(
    () => rows.map((r, i) => ({ ...r, _rank: i + 1 })),
    [rows],
  );

  const filteredSignals = useMemo(() => {
    if (signalsKind === "all") return signals;
    return signals.filter((s) => s.kind === signalsKind);
  }, [signals, signalsKind]);

  const hotTickers = useMemo(() => {
    const m = new Map<string, { fromSignals: number; fromResults: number }>();
    for (const s of signals) {
      const t = (s.ticker ?? "").trim();
      if (!t) continue;
      const cur = m.get(t) ?? { fromSignals: 0, fromResults: 0 };
      cur.fromSignals += 1;
      m.set(t, cur);
    }
    for (const r of rows) {
      const t = (r.ticker ?? "").trim();
      if (!t) continue;
      const cur = m.get(t) ?? { fromSignals: 0, fromResults: 0 };
      cur.fromResults += 1;
      m.set(t, cur);
    }
    return Array.from(m.entries())
      .map(([ticker, c]) => ({ ticker, ...c, score: c.fromSignals * 3 + c.fromResults }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);
  }, [rows, signals]);

  const hotProviders = useMemo(() => {
    const m = new Map<string, { fromSignals: number; fromTopResults: number }>();
    for (const s of signals) {
      const p = (s.provider ?? "").trim();
      if (!p) continue;
      const cur = m.get(p) ?? { fromSignals: 0, fromTopResults: 0 };
      cur.fromSignals += 1;
      m.set(p, cur);
    }
    for (const r of ranked.slice(0, 30)) {
      const p = (r.provider ?? "").trim();
      if (!p) continue;
      const cur = m.get(p) ?? { fromSignals: 0, fromTopResults: 0 };
      cur.fromTopResults += 1;
      m.set(p, cur);
    }
    return Array.from(m.entries())
      .map(([provider, c]) => ({ provider, ...c, score: c.fromSignals * 2 + c.fromTopResults * 3 }))
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);
  }, [ranked, signals]);

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="LEADERBOARD"
        subtitle="Results + signals in one screen. Use provider chips to focus copy-trade decisions."
        active="observe"
      />
      <div className="w-full px-4 py-6">
        <section className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Hot tickers
              </div>
              <div className="text-[10px] text-[var(--nexus-muted)]">
                signals×3 + results
              </div>
            </div>
            {hotTickers.length === 0 ? (
              <div className="mt-2 text-[11px] text-[var(--nexus-muted)]">
                Not enough symbol data yet. Publish signals with <code>ticker</code> or run backtests.
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {hotTickers.map((t) => (
                  <button
                    key={t.ticker}
                    type="button"
                    onClick={() => {
                      setSignalsKind("all");
                    }}
                    className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-2.5 py-1.5 text-[10px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
                    title={`signals=${t.fromSignals} results=${t.fromResults}`}
                  >
                    {t.ticker}{" "}
                    <span className="text-[rgba(138,149,166,0.9)]">
                      {t.fromSignals}/{t.fromResults}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Hot providers
              </div>
              <div className="text-[10px] text-[var(--nexus-muted)]">
                signals×2 + top-results×3
              </div>
            </div>
            {hotProviders.length === 0 ? (
              <div className="mt-2 text-[11px] text-[var(--nexus-muted)]">
                No providers yet. Publish results/signals to populate the marketplace view.
              </div>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {hotProviders.map((p) => {
                  const active = providerFilter === p.provider;
                  return (
                    <button
                      key={p.provider}
                      type="button"
                      onClick={() => setProviderFilter((cur) => (cur === p.provider ? "" : p.provider))}
                      className={`rounded-xl border px-2.5 py-1.5 text-[10px] transition ${
                        active
                          ? "border-[rgba(34,211,238,0.35)] bg-[rgba(34,211,238,0.10)] text-[rgba(226,232,240,0.95)]"
                          : "border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
                      }`}
                      title={`signals=${p.fromSignals} topResults=${p.fromTopResults}`}
                    >
                      {p.provider}
                    </button>
                  );
                })}
                <Link
                  href="/leadpage"
                  className="ml-auto text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
                  onClick={() => setProviderFilter("")}
                  title="Clear focus"
                >
                  clear focus
                </Link>
              </div>
            )}
          </div>
        </section>

        <div
          className={
            focus === "signals"
              ? "grid grid-cols-1 gap-4"
              : "grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]"
          }
        >
          {focus !== "signals" ? (
          <div className="min-w-0">
            <section className="flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                  Results
                </span>
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
                <span className="ml-auto text-[11px] text-[var(--nexus-muted)]">
                  {loading ? "Loading…" : `${ranked.length} rows`}
                </span>
              </div>

              {providers.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[11px] text-[var(--nexus-muted)]">Providers</span>
                  {providers
                    .filter((p) => p && p !== "local")
                    .slice(0, 18)
                    .map((p) => {
                      const active = providerFilter === p;
                      return (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setProviderFilter((cur) => (cur === p ? "" : p))}
                          className={`rounded-xl border px-2.5 py-1.5 text-[10px] transition ${
                            active
                              ? "border-[rgba(34,211,238,0.35)] bg-[rgba(34,211,238,0.10)] text-[rgba(226,232,240,0.95)]"
                              : "border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
                          }`}
                          title={active ? "Clear provider focus" : "Focus signals to this provider"}
                        >
                          {p}
                        </button>
                      );
                    })}
                  <Link
                    href={`/leadpage?focus=signals${
                      providerFilter.trim() ? `&provider=${encodeURIComponent(providerFilter.trim())}` : ""
                    }`}
                    className="ml-auto text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
                    title="Open signals focus"
                  >
                    open signals focus →
                  </Link>
                </div>
              ) : null}

              {error ? (
                <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
                  {error}
                </div>
              ) : null}
            </section>

            <section className="mt-4 overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
              <div className="overflow-auto">
                <table className="w-full min-w-[980px] border-separate border-spacing-0 text-left text-[11px]">
              <thead className="sticky top-0 z-10 bg-[rgba(6,8,11,0.9)] backdrop-blur">
                <tr className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                  <th className="px-3 py-3">Rank</th>
                  <th className="px-3 py-3">Source</th>
                  <th className="px-3 py-3">Run</th>
                  <th className="px-3 py-3">Title</th>
                  <th className="px-3 py-3">Ticker</th>
                  <th className="px-3 py-3">Return %</th>
                  <th className="px-3 py-3">Sharpe</th>
                  <th className="px-3 py-3">Max DD %</th>
                  <th className="px-3 py-3">Trades</th>
                  <th className="px-3 py-3">Steps</th>
                  <th className="px-3 py-3">When</th>
                </tr>
              </thead>
              <tbody>
                {ranked.length === 0 && !loading ? (
                  <tr>
                    <td className="px-3 py-6 text-[var(--nexus-muted)]" colSpan={11}>
                      <div className="flex flex-col gap-2">
                        <div>No results yet.</div>
                        <div>
                          Run a backtest to generate local summaries, or publish provider results
                          via <code>/leadpage/providers/&lt;provider&gt;/results</code> (see{" "}
                          <code>scripts/publish_leadpage_result.py</code>).
                        </div>
                        <div className="text-[10px] text-[var(--nexus-muted)]">
                          Tip: create a provider + key in{" "}
                          <Link className="underline" href="/platform/providers">
                            Platform → Providers
                          </Link>
                          .
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null}

                {ranked.map((r) => {
                  const src =
                    r.source === "external"
                      ? `external${r.provider ? `:${r.provider}` : ""}`
                      : (r.source ?? "—");
                  const ret = r.total_return_pct;
                  const retOk = typeof ret === "number" && Number.isFinite(ret);
                  const retCls = retOk
                    ? ret >= 0
                      ? "text-[rgba(0,212,170,0.92)]"
                      : "text-[rgba(242,92,84,0.95)]"
                    : "text-[var(--nexus-muted)]";
                  const scan = localScanStatus(r.meta);
                  const scanBadge =
                    scan === "executed"
                      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
                      : scan === "skipped"
                        ? "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]"
                        : scan
                          ? "border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] text-[rgba(226,232,240,0.92)]"
                          : null;

                  return (
                    <tr
                      key={`${r.source ?? "x"}:${r.provider ?? "p"}:${r.run_id ?? Math.random()}`}
                      className="border-t border-[rgba(138,149,166,0.12)] hover:bg-[rgba(255,255,255,0.02)]"
                    >
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">{fmtInt(r._rank)}</td>
                      <td className="px-3 py-3 text-[var(--nexus-muted)]">{src}</td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">
                        {r.provider ? (
                          <Link
                            href={`/leadpage/providers/${encodeURIComponent(r.provider)}${
                              r.run_id ? `?run=${encodeURIComponent(r.run_id)}` : ""
                            }`}
                            className="nexus-line-clamp-1 underline decoration-[rgba(138,149,166,0.35)] underline-offset-2 hover:decoration-[rgba(0,212,170,0.55)]"
                            title="Open provider analytics"
                          >
                            {r.run_id ?? "—"}
                          </Link>
                        ) : (
                          <span className="nexus-line-clamp-1">{r.run_id ?? "—"}</span>
                        )}
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.85)]">
                        <span className="nexus-line-clamp-1">{r.title ?? "—"}</span>
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.85)]">{r.ticker ?? "—"}</td>
                      <td className={`px-3 py-3 font-semibold tabular-nums ${retCls}`}>
                        <div className="flex items-center gap-2">
                          <span>{fmtPct(ret, 2)}</span>
                          {scan && scanBadge ? (
                            <span
                              className={`rounded-lg border px-2 py-1 text-[9px] uppercase tracking-[0.16em] ${scanBadge}`}
                              title="Local scan execution status"
                            >
                              {scan}
                            </span>
                          ) : null}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)] tabular-nums">{fmtNum(r.sharpe, 3)}</td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)] tabular-nums">
                        {fmtNum(r.max_drawdown_pct, 2)}
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">
                        {typeof r.trade_count === "number" ? r.trade_count : "—"}
                      </td>
                      <td className="px-3 py-3 text-[rgba(226,232,240,0.9)]">
                        {typeof r.steps === "number" ? r.steps : "—"}
                      </td>
                      <td className="px-3 py-3 text-[var(--nexus-muted)]">{fmtTs(r.ts)}</td>
                    </tr>
                  );
                })}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
          ) : null}

          <aside className="min-w-0" id="signals">
            <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                  Signals
                </div>
                {focus === "signals" ? (
                  <Link
                    href="/leadpage"
                    className="text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
                    title="Back to overview"
                  >
                    back to overview →
                  </Link>
                ) : null}
                {providerFilter ? (
                  <span className="rounded-lg border border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] px-2 py-1 text-[9px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.92)]">
                    provider: {providerFilter}
                  </span>
                ) : (
                  <span className="text-[10px] text-[var(--nexus-muted)]">global</span>
                )}
                {providerFilter ? (
                  <button
                    type="button"
                    onClick={() => setProviderFilter("")}
                    className="text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
                    title="Clear provider focus"
                  >
                    clear
                  </button>
                ) : null}
                <span className="ml-auto text-[10px] text-[var(--nexus-muted)]">
                  {signalsLoading ? "Loading…" : `${filteredSignals.length} items`}
                </span>
              </div>

              <div className="mt-3 flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-[var(--nexus-muted)]">Filter</span>
                <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
                  {(["all", "strategy", "ops", "discussion"] as const).map((k) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setSignalsKind(k)}
                      className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
                        signalsKind === k ? "is-active" : ""
                      }`}
                    >
                      {k}
                    </button>
                  ))}
                </div>
              </div>

              {signalsError ? (
                <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
                  {signalsError}
                </div>
              ) : null}

              <div className="mt-4 flex max-h-[840px] flex-col gap-3 overflow-auto pr-1">
                {!signalsLoading && filteredSignals.length === 0 ? (
                  <div className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-3 text-[11px] text-[var(--nexus-muted)]">
                    No signals yet. Providers can publish to <code>/signals/publish</code>.
                  </div>
                ) : null}

                {filteredSignals.map((s) => {
                  const kindBadge =
                    s.kind === "ops"
                      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
                      : s.kind === "strategy"
                        ? "border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] text-[rgba(226,232,240,0.92)]"
                        : "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]";
                  return (
                    <article
                      key={s.id}
                      className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-wrap items-center gap-2">
                          <span
                            className={`rounded-lg border px-2 py-1 text-[9px] uppercase tracking-[0.16em] ${kindBadge}`}
                          >
                            {s.kind}
                          </span>
                          <Link
                            href={`/leadpage/providers/${encodeURIComponent(s.provider)}`}
                            className="text-[11px] text-[rgba(226,232,240,0.9)] hover:text-white"
                            title="Open provider performance"
                          >
                            {s.provider}
                          </Link>
                          {s.ticker ? (
                            <span className="text-[10px] text-[var(--nexus-muted)]">{s.ticker}</span>
                          ) : null}
                        </div>
                        <div className="text-[10px] text-[var(--nexus-muted)]">{fmtTs(s.ts)}</div>
                      </div>
                      <h3 className="mt-2 text-[12px] font-semibold text-[rgba(226,232,240,0.95)]">
                        {s.title}
                      </h3>
                      <p className="mt-2 whitespace-pre-wrap break-words text-[11px] text-[rgba(226,232,240,0.84)]">
                        {s.body.length > 420 ? `${s.body.slice(0, 420)}…` : s.body}
                      </p>
                      {s.kind === "ops" ? (
                        <div className="mt-3 text-[10px] text-[var(--nexus-muted)]">
                          Tip: ops updates route into <Link className="underline" href="/inbox">Approvals</Link> when you follow the provider.
                        </div>
                      ) : null}
                    </article>
                  );
                })}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
