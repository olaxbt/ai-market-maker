"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

/* ── Types (mirrors leaderboard page) ── */

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

/* ── Helpers (mirrors leaderboard page) ── */

function fmtPct(v: unknown, d = 2) {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(d)}%`;
}
function fmtNum(v: unknown, d = 2) {
  return typeof v === "number" && Number.isFinite(v) ? v.toFixed(d) : "—";
}
function fmtInt(v: unknown) {
  return typeof v === "number" && Number.isFinite(v) ? Math.round(v).toString() : "—";
}
function fmtTsRel(ts: unknown) {
  if (typeof ts !== "number" || !Number.isFinite(ts)) return "—";
  const s = Math.floor((Date.now() - ts * 1000) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 3600)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

/* ── Component ── */

export default function LeaderboardPanel() {
  const [tab, setTab] = useState<"runs" | "signals">("runs");
  const [rows, setRows] = useState<LeaderboardRow[]>([]);
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const [loading, setLoading] = useState(true);
  const rowsRef = useRef<LeaderboardRow[]>([]);

  /* Fetch runs */
  useEffect(() => {
    if (tab !== "runs") return;
    let c = false;
    if (rowsRef.current.length === 0) setLoading(true);
    async function load() {
      try {
        const res = await fetch(`/api/leadpage/leaderboard?limit=25&sort_by=return`, { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (c) return;
        const n = Array.isArray(json?.rows) ? json.rows : [];
        if (JSON.stringify(rowsRef.current) !== JSON.stringify(n)) {
          setRows(n);
          rowsRef.current = n;
        }
      } catch {
        /* ignore */
      } finally {
        if (!c) setLoading(false);
      }
    }
    load();
    const t = setInterval(load, 15_000);
    return () => {
      c = true;
      clearInterval(t);
    };
  }, [tab]);

  /* Fetch signals */
  useEffect(() => {
    if (tab !== "signals") return;
    let c = false;
    async function load() {
      try {
        const res = await fetch("/api/signals/feed?limit=10", { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (c) return;
        setSignals(Array.isArray(json?.signals) ? (json.signals as Signal[]) : []);
      } catch {
        if (!c) setSignals([]);
      }
    }
    void load();
    const t = setInterval(load, 20_000);
    return () => {
      c = true;
      clearInterval(t);
    };
  }, [tab]);

  const ranked = useMemo(() => rows.map((r, i) => ({ ...r, _rank: i + 1 })), [rows]);

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header with tab toggle */}
      <div className="flex items-center justify-between border-b border-[rgba(138,149,166,0.08)] px-4 py-2.5">
        <div className="inline-flex rounded-lg bg-[rgba(6,8,11,0.35)] p-0.5">
          <button
            type="button"
            onClick={() => setTab("runs")}
            className={`rounded-lg px-3 py-1 text-[10px] font-medium transition ${
              tab === "runs"
                ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.92)]"
                : "text-[rgba(138,149,166,0.6)] hover:text-[rgba(226,232,240,0.8)]"
            }`}
          >
            Runs
          </button>
          <button
            type="button"
            onClick={() => setTab("signals")}
            className={`rounded-lg px-3 py-1 text-[10px] font-medium transition ${
              tab === "signals"
                ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.92)]"
                : "text-[rgba(138,149,166,0.6)] hover:text-[rgba(226,232,240,0.8)]"
            }`}
          >
            Signals
          </button>
        </div>
        <div className="flex items-center gap-3">
          <a
            href="/leaderboard"
            className="rounded-lg border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.25)] px-2 py-1 text-[9px] uppercase tracking-[0.18em] text-[rgba(138,149,166,0.55)] hover:text-[rgba(226,232,240,0.85)]"
          >
            Open full leaderboard
          </a>
          <span className="text-[9px] tracking-[0.2em] text-[rgba(138,149,166,0.35)] uppercase">
            Ranked runs &amp; signals
          </span>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-3">
        <div className="mb-3 rounded-lg border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.22)] p-3 text-[10px] text-[rgba(138,149,166,0.55)]">
          Want to contribute? Ask Studio: <span className="font-mono text-[rgba(226,232,240,0.75)]">publish to leaderboard</span>
        </div>
        {tab === "runs" ? (
          loading && ranked.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-[rgba(0,212,170,0.4)] border-t-transparent" />
            </div>
          ) : ranked.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-[11px] text-[rgba(138,149,166,0.5)]">
              No results yet.
            </div>
          ) : (
            <table className="w-full text-left text-[11px]">
              <thead>
                <tr className="text-[9px] uppercase tracking-[0.15em] text-[rgba(138,149,166,0.5)]">
                  <th className="w-7 pb-1.5 pr-1">#</th>
                  <th className="pb-1.5 pr-2">Source</th>
                  <th className="pb-1.5 pr-2">Ticker</th>
                  <th className="pb-1.5 pr-2 text-right">Return</th>
                  <th className="pb-1.5 pr-2 text-right">Sharpe</th>
                  <th className="pb-1.5 pr-2 text-right">DD%</th>
                  <th className="pb-1.5 text-right">Trades</th>
                </tr>
              </thead>
              <tbody>
                {ranked.map((r) => {
                  const ret = r.total_return_pct;
                  const ok = typeof ret === "number" && Number.isFinite(ret);
                  const pos = ok && ret! >= 0;
                  const provider = r.provider?.trim() || "Anonymous";
                  return (
                    <tr
                      key={`${r.source ?? "x"}:${r.provider ?? "p"}:${r.run_id ?? "norun"}`}
                      className="border-t border-[rgba(138,149,166,0.05)] transition-colors hover:bg-[rgba(255,255,255,0.02)]"
                    >
                      <td className="py-2 pr-1 font-mono text-[rgba(226,232,240,0.4)]">{r._rank}</td>
                      <td className="py-2 pr-2 text-[rgba(226,232,240,0.85)]">{provider}</td>
                      <td className="py-2 pr-2">
                        {r.ticker ? (
                          <span className="rounded border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.25)] px-1.5 py-0.5 text-[9px] font-mono text-[rgba(226,232,240,0.6)]">
                            {r.ticker}
                          </span>
                        ) : (
                          <span className="text-[rgba(138,149,166,0.4)]">—</span>
                        )}
                      </td>
                      <td className={`py-2 pr-2 text-right font-semibold tabular-nums ${
                        pos ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"
                      }`}>
                        {fmtPct(ret, 2)}
                      </td>
                      <td className="py-2 pr-2 text-right font-mono tabular-nums text-[rgba(226,232,240,0.65)]">
                        {fmtNum(r.sharpe, 2)}
                      </td>
                      <td className="py-2 pr-2 text-right font-mono tabular-nums text-[rgba(242,92,84,0.7)]">
                        {fmtNum((r as any).max_drawdown_pct ?? (r as any).max_drawdown ?? 0, 1)}
                      </td>
                      <td className="py-2 text-right font-mono tabular-nums text-[rgba(226,232,240,0.65)]">
                        {fmtInt(r.trade_count)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )
        ) : (
          /* Signals tab */
          signals === null ? (
            <div className="flex items-center justify-center py-12">
              <div className="h-5 w-5 animate-spin rounded-full border-2 border-[rgba(0,212,170,0.4)] border-t-transparent" />
            </div>
          ) : signals.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-[11px] text-[rgba(138,149,166,0.5)]">
              No signals yet.
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {signals.map((s) => {
                const kb =
                  s.kind === "ops"
                    ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
                    : s.kind === "strategy"
                      ? "border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] text-[rgba(226,232,240,0.92)]"
                      : "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]";
                return (
                  <div key={s.id} className="rounded-lg border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.2)] p-2.5">
                    <div className="mb-1 flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5">
                        <span className={`rounded border px-1.5 py-0.5 text-[8px] uppercase tracking-[0.16em] ${kb}`}>
                          {s.kind}
                        </span>
                        {s.ticker ? (
                          <span className="font-mono text-[9px] text-[rgba(138,149,166,0.5)]">{s.ticker}</span>
                        ) : null}
                      </div>
                      <span className="text-[9px] text-[rgba(138,149,166,0.4)]">{fmtTsRel(s.ts)}</span>
                    </div>
                    <div className="text-[11px] font-medium leading-tight text-[rgba(226,232,240,0.92)]">{s.title}</div>
                    {s.body ? (
                      <p className="mt-1 text-[10px] leading-relaxed text-[rgba(226,232,240,0.6)]">
                        {s.body.length > 140 ? `${s.body.slice(0, 140)}…` : s.body}
                      </p>
                    ) : null}
                    <div className="mt-1 text-[8px] text-[rgba(138,149,166,0.4)]">{s.provider}</div>
                  </div>
                );
              })}
            </div>
          )
        )}
      </div>
    </div>
  );
}
