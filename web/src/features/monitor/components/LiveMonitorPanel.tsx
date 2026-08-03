"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type {
  BarsResponse,
  EquitySeriesResponse,
  SummaryPayload,
} from "@/types/backtest";
import { EmptySessionPanel } from "@/components/EmptySessionPanel";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type PortfolioHealth = {
  account_id?: string;
  ts?: number;
  mode?: string;
  balances?: Record<string, number>;
  positions?: unknown[];
  risk_caps?: Record<string, unknown>;
  free_cash_usdt?: number;
  margin_locked_usdt?: number;
  equity_usdt?: number;
  error?: string;
  hint?: string;
};

function fmtUsd(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return `$${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function fmtNum(x: number | null | undefined, maxFrac = 4): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return x.toLocaleString(undefined, { maximumFractionDigits: maxFrac });
}

function safeDate(ts: number | null | undefined): Date | null {
  if (!ts || !Number.isFinite(ts)) return null;
  const ms = ts > 1e12 ? ts : ts * 1000;
  const d = new Date(ms);
  return Number.isNaN(d.getTime()) ? null : d;
}

function formatTimeShort(ts: number | null | undefined): string {
  const d = safeDate(ts);
  if (!d) return "—";
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** Parse API timestamps that may be seconds or ms, or numeric strings. */
function coerceUnixMs(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === "number" ? v : typeof v === "string" ? Number(v) : NaN;
  if (!Number.isFinite(n) || n <= 0) return null;
  // Engine uses ms (≈1.7e12). If value looks like Unix seconds (~1.7e9), scale up.
  return n < 1e12 ? n * 1000 : n;
}

/** Axis labels: include date when the visible range spans multiple days. */
function formatChartTickLabel(ms: number, rangeMs: number): string {
  if (!Number.isFinite(ms) || ms <= 0) return "—";
  const d = new Date(ms);
  if (Number.isNaN(d.getTime())) return "—";
  const spanDays = rangeMs / (24 * 60 * 60 * 1000);
  if (spanDays >= 2) {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }
  if (spanDays >= 0.5) {
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function pickEquityPointMs(
  p: unknown,
  idx: number,
  intervalSec: number,
  barTsByIndex: Array<number | undefined>,
): number {
  if (!p || typeof p !== "object") return idx * intervalSec * 1000;
  const o = p as Record<string, unknown>;
  const direct =
    coerceUnixMs(o.timestamp) ??
    coerceUnixMs(o.ts_ms) ??
    coerceUnixMs(o.bar_ts_ms) ??
    coerceUnixMs(o.time_ms);
  if (direct != null) return direct;
  const fromBar = coerceUnixMs(barTsByIndex[idx]);
  if (fromBar != null) return fromBar;
  const firstBar = coerceUnixMs(barTsByIndex[0]);
  if (firstBar != null) return firstBar + idx * intervalSec * 1000;
  const step = typeof o.step === "number" && Number.isFinite(o.step) ? o.step : idx;
  return step * intervalSec * 1000;
}

function pct(x: number | null | undefined, digits = 2): string {
  if (x == null || !Number.isFinite(x)) return "—";
  const s = x >= 0 ? "+" : "";
  return `${s}${x.toFixed(digits)}%`;
}

/** Max drawdown magnitude (0–100): no "+" prefix (would read like a gain). */
function fmtDrawdownPct(x: number | null | undefined, digits = 2): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return `${x.toFixed(digits)}%`;
}

type BalancePoint = { ts: number; totalUsd: number; usdt: number };

function totalFromBalances(balances: Record<string, number>): number {
  const stableLike = new Set(["USD", "USDT", "USDC", "DAI", "FDUSD", "TUSD"]);
  let total = 0;
  for (const [k, v] of Object.entries(balances)) {
    if (typeof v !== "number" || !Number.isFinite(v)) continue;
    if (stableLike.has(k.toUpperCase())) total += v;
  }
  return total;
}

type TapeEntry = {
  seq: number;
  kind: string;
  node_id: string;
  ts: string;
  message: string;
};

function pickString(obj: unknown, keys: string[]): string | null {
  if (!obj || typeof obj !== "object") return null;
  const o = obj as Record<string, unknown>;
  for (const k of keys) {
    const v = o[k];
    if (typeof v === "string" && v.trim()) return v;
  }
  return null;
}

function pickNumber(obj: unknown, keys: string[]): number | null {
  if (!obj || typeof obj !== "object") return null;
  const o = obj as Record<string, unknown>;
  for (const k of keys) {
    const v = o[k];
    if (typeof v === "number" && Number.isFinite(v)) return v;
    if (typeof v === "string") {
      const n = Number(v);
      if (Number.isFinite(n)) return n;
    }
  }
  return null;
}

const MONITOR_KPI_SHELL = [
  "ring-1 ring-cyan-500/30 bg-[linear-gradient(135deg,rgba(34,211,238,0.14),rgba(6,8,11,0.55))]",
  "ring-1 ring-blue-500/30 bg-[linear-gradient(135deg,rgba(59,130,246,0.14),rgba(6,8,11,0.55))]",
  "ring-1 ring-violet-500/30 bg-[linear-gradient(135deg,rgba(139,92,246,0.14),rgba(6,8,11,0.55))]",
  "ring-1 ring-emerald-500/30 bg-[linear-gradient(135deg,rgba(52,211,153,0.12),rgba(6,8,11,0.55))]",
  "ring-1 ring-amber-500/30 bg-[linear-gradient(135deg,rgba(245,158,11,0.12),rgba(6,8,11,0.55))]",
  "ring-1 ring-fuchsia-500/30 bg-[linear-gradient(135deg,rgba(217,70,239,0.12),rgba(6,8,11,0.55))]",
  "ring-1 ring-sky-500/25 bg-[linear-gradient(135deg,rgba(14,165,233,0.12),rgba(6,8,11,0.55))]",
] as const;

export function LiveMonitorPanel({
  sessionActive = false,
}: {
  sessionActive?: boolean;
}) {
  const [health, setHealth] = useState<PortfolioHealth | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [history, setHistory] = useState<BalancePoint[]>([]);
  const [resetBusy, setResetBusy] = useState(false);
  const [resetMsg, setResetMsg] = useState<string | null>(null);

  const refreshHealth = useCallback(async () => {
    const res = await fetch("/api/pm/portfolio-health", { cache: "no-store" });
    const data = (await res.json().catch(() => ({}))) as PortfolioHealth;
    if (!res.ok) {
      setErr(typeof data.error === "string" ? data.error : "Failed to load portfolio health");
      return;
    }
    setErr(null);
    setHealth(data);
    const equity =
      typeof data.equity_usdt === "number"
        ? data.equity_usdt
        : typeof data.balances?.USDT === "number"
          ? data.balances.USDT
          : 0;
    const free =
      typeof data.free_cash_usdt === "number"
        ? data.free_cash_usdt
        : typeof data.balances?.USDT === "number"
          ? data.balances.USDT
          : 0;
    const nowTs = typeof data.ts === "number" ? data.ts : Math.floor(Date.now() / 1000);
    setHistory((prev) => {
      const next = [...prev, { ts: nowTs, totalUsd: equity, usdt: free }];
      const trimmed = next.slice(-140);
      const out: BalancePoint[] = [];
      const seen = new Set<number>();
      for (const p of trimmed) {
        if (seen.has(p.ts)) continue;
        out.push(p);
        seen.add(p.ts);
      }
      return out;
    });
  }, []);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        await refreshHealth();
      } catch {
        if (!cancelled) setErr("Failed to load portfolio health");
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [refreshHealth]);

  const resetBook = useCallback(async () => {
    if (sessionActive) {
      setResetMsg("Stop the live session before resetting the book.");
      return;
    }
    setResetBusy(true);
    setResetMsg(null);
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/paper/book/reset`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = (await res.json().catch(() => ({}))) as { detail?: string };
      if (!res.ok) {
        setResetMsg(typeof data.detail === "string" ? data.detail : "Reset failed");
        return;
      }
      setHistory([]);
      setResetMsg("Book restored to starting capital.");
      await refreshHealth();
    } catch (e) {
      setResetMsg(e instanceof Error ? e.message : "Reset failed");
    } finally {
      setResetBusy(false);
    }
  }, [refreshHealth, sessionActive]);

  const balances = useMemo(() => health?.balances ?? {}, [health?.balances]);
  const equityUsd =
    typeof health?.equity_usdt === "number"
      ? health.equity_usdt
      : typeof balances.USDT === "number"
        ? balances.USDT
        : null;
  const freeCash =
    typeof health?.free_cash_usdt === "number" ? health.free_cash_usdt : null;
  const marginLocked =
    typeof health?.margin_locked_usdt === "number" ? health.margin_locked_usdt : null;
  const usdt = equityUsd;
  const totalStable = equityUsd;
  const status = sessionActive ? "active" : "idle";

  const useReplay = false;
  const replayEnabled = false;
  const replaySummary = null as SummaryPayload | null;
  const replayEquity = null as EquitySeriesResponse | null;
  const replayBars = null as BarsResponse | null;

  const cards = useMemo(
    () => [
      {
        label: "Book equity",
        value: fmtUsd(equityUsd),
        tone: "text-[#00d4aa]",
      },
      {
        label: "Free cash",
        value: fmtUsd(freeCash),
        tone: "text-[#22d3ee]",
      },
      {
        label: "Margin locked",
        value: fmtUsd(marginLocked),
        tone: "text-[#fbbf24]",
      },
      {
        label: "Mode",
        value: health?.mode ? String(health.mode) : "—",
        tone: "text-[#a78bfa]",
      },
      {
        label: "Open positions",
        value: String(Array.isArray(health?.positions) ? health.positions.length : 0),
        tone: "text-[var(--nexus-text)]",
      },
      {
        label: "Session",
        value: sessionActive ? status || "active" : "idle",
        tone: "text-[var(--nexus-muted)]",
      },
    ],
    [
      equityUsd,
      freeCash,
      marginLocked,
      health?.mode,
      health?.positions,
      sessionActive,
      status,
    ],
  );

  const chartData = useMemo(
    () =>
      history.map((p) => ({
        ts: p.ts,
        t: formatTimeShort(p.ts),
        totalUsd: p.totalUsd,
        usdt: p.usdt,
      })),
    [history],
  );

  const replayIntervalSec = Math.max(
    60,
    replaySummary?.interval_sec ?? replayBars?.interval_sec ?? 300,
  );

  const replayChartData = useMemo(() => {
    if (!replayEnabled || !replayEquity?.points?.length) return [];
    const barTsByIndex = (replayBars?.bars ?? []).map((b) => {
      const n = coerceUnixMs(b.ts_ms);
      return n ?? undefined;
    });
    return replayEquity.points.map((p, idx) => {
      const anyP = p as unknown as { cash?: unknown };
      const ts = pickEquityPointMs(p, idx, replayIntervalSec, barTsByIndex);
      const cash = (anyP as { cash?: unknown }).cash;
      const cashNum = typeof cash === "number" && Number.isFinite(cash) ? cash : null;
      return { ts, t: formatTimeShort(ts), totalUsd: p.equity, usdt: cashNum ?? 0 };
    });
  }, [replayBars?.bars, replayEnabled, replayEquity?.points, replayIntervalSec]);

  const assetPriceRows = useMemo(() => {
    if (useReplay && replayBars?.bars?.length) {
      const iv = Math.max(1, replayBars.interval_sec ?? 60);
      return replayBars.bars.map((b, i) => {
        let ts = coerceUnixMs(b.ts_ms);
        if (ts == null) {
          const base = coerceUnixMs(replayBars.bars[0]?.ts_ms);
          const step = typeof b.step === "number" && Number.isFinite(b.step) ? b.step : i;
          ts = (base ?? 0) + step * iv * 1000;
        }
        return { ts, t: formatTimeShort(ts), close: b.close };
      });
    }
    return [];
  }, [replayBars?.bars, replayBars?.interval_sec, useReplay]);

  const effectiveChart = useReplay ? replayChartData : chartData;
  const chartRows = effectiveChart;

  const chartTimeRangeMs = useMemo(() => {
    if (chartRows.length < 2) return 0;
    const a = chartRows[0]?.ts;
    const b = chartRows[chartRows.length - 1]?.ts;
    if (typeof a !== "number" || typeof b !== "number") return 0;
    return Math.abs(b - a);
  }, [chartRows]);

  const assetTimeRangeMs = useMemo(() => {
    if (assetPriceRows.length < 2) return 0;
    const a = assetPriceRows[0]?.ts;
    const b = assetPriceRows[assetPriceRows.length - 1]?.ts;
    if (typeof a !== "number" || typeof b !== "number") return 0;
    return Math.abs(b - a);
  }, [assetPriceRows]);

  const seriesStats = useMemo(() => {
    const rows = chartRows;
    if (!rows.length) return null;
    const first = rows[0];
    const last = rows[rows.length - 1];
    const v0 = typeof first.totalUsd === "number" ? first.totalUsd : NaN;
    const vN = typeof last.totalUsd === "number" ? last.totalUsd : NaN;
    if (!Number.isFinite(v0) || !Number.isFinite(vN) || v0 <= 0) return null;
    let lo = Number.POSITIVE_INFINITY;
    let hi = Number.NEGATIVE_INFINITY;
    let peak = Number.NEGATIVE_INFINITY;
    let maxDdPct = 0;
    for (const r of rows) {
      const v = typeof r.totalUsd === "number" ? r.totalUsd : NaN;
      if (!Number.isFinite(v)) continue;
      lo = Math.min(lo, v);
      hi = Math.max(hi, v);
      if (v > peak) peak = v;
      if (peak > 0) {
        const dd = ((peak - v) / peak) * 100;
        if (dd > maxDdPct) maxDdPct = dd;
      }
    }
    const retPct = ((vN - v0) / v0) * 100;
    return {
      startUsd: v0,
      endUsd: vN,
      pnlUsd: vN - v0,
      retPct,
      lo,
      hi,
      /** Peak-to-trough max drawdown along the curve (0–100), not (global high − low) / high. */
      ddPct: maxDdPct,
      points: rows.length,
      lastTs: typeof last.ts === "number" ? last.ts : null,
    };
  }, [chartRows]);

  const allocation = useMemo(() => {
    const rows = Object.entries(balances)
      .filter(([, v]) => typeof v === "number" && Number.isFinite(v) && v !== 0)
      .map(([asset, v]) => ({ asset, value: Math.abs(v) }));
    rows.sort((a, b) => b.value - a.value);
    return rows.slice(0, 8);
  }, [balances]);

  const allocationTotal = useMemo(
    () => allocation.reduce((s, r) => s + (Number.isFinite(r.value) ? r.value : 0), 0),
    [allocation],
  );
  const allocationColors = [
    "#00D4AA",
    "#3B82F6",
    "#A78BFA",
    "#F59E0B",
    "#FB7185",
    "#22D3EE",
    "#34D399",
    "#F97316",
  ];

  const positions = Array.isArray(health?.positions) ? health?.positions : [];

  if (!health && !err) {
    return (
      <EmptySessionPanel
        title="Loading portfolio…"
        body="Fetching the live trading book (paper or live account)."
      />
    );
  }

  return (
    <div className="nexus-bg min-h-0 flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-6xl px-4 py-3 pb-10 pt-14 space-y-6">
        <div className="overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[radial-gradient(900px_360px_at_20%_0%,rgba(34,211,238,0.14),transparent_60%),radial-gradient(800px_340px_at_85%_10%,rgba(167,139,250,0.12),transparent_60%),radial-gradient(900px_360px_at_55%_110%,rgba(245,158,11,0.10),transparent_65%)] px-5 py-4 shadow-[0_0_28px_rgba(0,212,170,0.06)]">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-glow)]">
                Live book
              </p>
              <h2 className="mt-1 text-lg font-semibold tracking-tight text-[var(--nexus-text)]">
                Portfolio
              </h2>
              <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-[var(--nexus-muted)]">
                Live account equity, free cash, positions, and risk. Historical backtest PnL and
                candle charts stay in{" "}
                <a
                  href="/console?view=research"
                  className="text-[var(--nexus-glow)] underline-offset-2 hover:underline"
                >
                  Research → Saved run
                </a>
                .
              </p>
              {resetMsg ? (
                <p className="mt-2 font-mono text-[10px] text-[var(--nexus-muted)]">{resetMsg}</p>
              ) : null}
            </div>
            <button
              type="button"
              disabled={resetBusy || sessionActive}
              onClick={() => void resetBook()}
              title={
                sessionActive
                  ? "Stop the live session before resetting the book"
                  : "Reset paper book to starting capital and clear positions"
              }
              className="shrink-0 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[rgba(248,113,113,0.35)] hover:text-[rgba(248,113,113,0.95)] disabled:cursor-not-allowed disabled:opacity-40"
            >
              {resetBusy ? "Resetting…" : "Reset book"}
            </button>
          </div>
        </div>

        {err ? (
          <div className="rounded-lg border border-red-900/45 bg-red-950/35 px-4 py-3 font-mono text-xs text-red-100">
            {err}
          </div>
        ) : null}

        {/* KPI strip */}
        <section className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {cards.map((c, idx) => (
            <div
              key={c.label}
              className={`min-h-[4.25rem] rounded-xl px-3 py-2.5 sm:px-4 sm:py-3 ${MONITOR_KPI_SHELL[idx % MONITOR_KPI_SHELL.length]}`}
            >
              <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                {c.label}
              </p>
              <p className={`mt-1 truncate font-mono text-sm ${c.tone}`} title={c.value}>
                {c.value}
              </p>
            </div>
          ))}
        </section>

        {/* HERO */}
        <section className="grid gap-3 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
          <div className="overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[radial-gradient(1000px_420px_at_15%_-10%,rgba(249,115,22,0.16),transparent_58%),radial-gradient(900px_400px_at_85%_0%,rgba(59,130,246,0.12),transparent_60%),radial-gradient(900px_420px_at_50%_120%,rgba(245,158,11,0.10),transparent_62%)] p-5 shadow-[0_0_32px_rgba(245,158,11,0.12)]">
            <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
              <div className="min-w-0">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                  Portfolio equity curve
                </p>
                <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1">
                  <div className="font-mono text-2xl font-semibold tracking-tight text-[var(--nexus-text)]">
                    {fmtUsd(seriesStats?.endUsd ?? null)}
                  </div>
                  <div className="font-mono text-[12px] text-[var(--nexus-muted)]">
                    PnL{" "}
                    <span
                      className={
                        seriesStats && seriesStats.pnlUsd >= 0 ? "text-[#34d399]" : "text-[#fb7185]"
                      }
                    >
                      {fmtUsd(seriesStats?.pnlUsd ?? null)}
                    </span>{" "}
                    <span
                      className={
                        seriesStats && seriesStats.retPct >= 0 ? "text-[#34d399]" : "text-[#fb7185]"
                      }
                    >
                      ({pct(seriesStats?.retPct ?? null, 2)})
                    </span>
                  </div>
                </div>
                <div className="mt-1 font-mono text-[10px] text-[var(--nexus-muted)]">
                  <>
                    Live book · equity {fmtUsd(equityUsd)}
                    {freeCash != null ? (
                      <>
                        {" "}
                        · free <span className="text-[var(--nexus-text)]">{fmtUsd(freeCash)}</span>
                      </>
                    ) : null}
                    {sessionActive ? (
                      <>
                        {" "}
                        · session <span className="text-[var(--nexus-text)]">live</span>
                      </>
                    ) : null}
                  </>
                </div>
              </div>

              <div className="grid shrink-0 grid-cols-3 gap-2">
                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(167,139,250,0.16),rgba(167,139,250,0.04))] px-3 py-2">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Max DD
                  </p>
                  <p className="mt-1 font-mono text-[12px] text-[#c4b5fd]">
                    {fmtDrawdownPct(seriesStats?.ddPct ?? null, 2)}
                  </p>
                </div>
                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(59,130,246,0.18),rgba(59,130,246,0.04))] px-3 py-2">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    High
                  </p>
                  <p className="mt-1 font-mono text-[12px] text-[#60a5fa]">
                    {fmtUsd(seriesStats?.hi ?? null)}
                  </p>
                </div>
                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(251,113,133,0.16),rgba(251,113,133,0.04))] px-3 py-2">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Low
                  </p>
                  <p className="mt-1 font-mono text-[12px] text-[#fb7185]">
                    {fmtUsd(seriesStats?.lo ?? null)}
                  </p>
                </div>
              </div>
            </div>

            <div className="mt-3 h-[360px] min-h-[360px] w-full rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/10 p-2 shadow-[inset_0_0_0_1px_rgba(245,158,11,0.14)]">
              <ResponsiveContainer width="100%" height="100%" minHeight={320} minWidth={320}>
                <AreaChart data={chartRows} margin={{ left: 14, right: 14, top: 8, bottom: 0 }}>
                  <defs>
                    <linearGradient id="heroArea" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#F59E0B" stopOpacity={0.38} />
                      <stop offset="40%" stopColor="#F97316" stopOpacity={0.18} />
                      <stop offset="72%" stopColor="#FB923C" stopOpacity={0.08} />
                      <stop offset="100%" stopColor="#EA580C" stopOpacity={0.03} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(226,232,240,0.08)" vertical={false} />
                  <XAxis
                    dataKey="ts"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    scale="time"
                    tick={{ fill: "rgba(138,149,166,0.92)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={28}
                    tickFormatter={(v) => formatChartTickLabel(Number(v), chartTimeRangeMs)}
                  />
                  <YAxis
                    tick={{ fill: "rgba(138,149,166,0.92)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={64}
                    tickFormatter={(v) =>
                      `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(10,13,18,0.92)",
                      border: "1px solid rgba(138,149,166,0.22)",
                      borderRadius: 10,
                      fontFamily:
                        "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 11,
                    }}
                    formatter={(v: unknown) => fmtUsd(typeof v === "number" ? v : null)}
                    labelFormatter={(l) => formatChartTickLabel(Number(l), chartTimeRangeMs)}
                  />
                  <Area
                    type="monotone"
                    dataKey="totalUsd"
                    stroke="#F59E0B"
                    strokeWidth={2.8}
                    fill="url(#heroArea)"
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Lower row: half-width price + half-width quick analytics */}
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              <div className="overflow-hidden rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/10 p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                    Asset price (waiting for live OHLC)
                  </p>
                  <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                    {assetPriceRows.length ? `${assetPriceRows.length} pts` : "—"}
                  </p>
                </div>
                <div className="mt-2 h-[140px] min-h-[140px] w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-black/5 p-2 shadow-[inset_0_0_0_1px_rgba(34,211,238,0.12)]">
                  {assetPriceRows.length ? (
                    <ResponsiveContainer width="100%" height="100%" minHeight={120} minWidth={260}>
                      <AreaChart
                        data={assetPriceRows}
                        margin={{ left: 12, right: 12, top: 6, bottom: 0 }}
                      >
                        <defs>
                          <linearGradient id="assetArea" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="0%" stopColor="#22d3ee" stopOpacity={0.34} />
                            <stop offset="45%" stopColor="#3B82F6" stopOpacity={0.12} />
                            <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.04} />
                          </linearGradient>
                        </defs>
                        <CartesianGrid stroke="rgba(226,232,240,0.08)" vertical={false} />
                        <XAxis
                          dataKey="ts"
                          type="number"
                          domain={["dataMin", "dataMax"]}
                          scale="time"
                          tick={{ fill: "rgba(138,149,166,0.92)", fontSize: 10 }}
                          tickLine={false}
                          axisLine={false}
                          minTickGap={28}
                          tickFormatter={(v) => formatChartTickLabel(Number(v), assetTimeRangeMs)}
                        />
                        <YAxis
                          tick={{ fill: "rgba(138,149,166,0.92)", fontSize: 10 }}
                          tickLine={false}
                          axisLine={false}
                          width={56}
                          tickFormatter={(v) =>
                            Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })
                          }
                        />
                        <Tooltip
                          contentStyle={{
                            background: "rgba(10,13,18,0.92)",
                            border: "1px solid rgba(138,149,166,0.22)",
                            borderRadius: 10,
                            fontFamily:
                              "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                            fontSize: 11,
                          }}
                          formatter={(v: unknown) => fmtNum(typeof v === "number" ? v : null, 2)}
                          labelFormatter={(l) => formatChartTickLabel(Number(l), assetTimeRangeMs)}
                        />
                        <Area
                          type="monotone"
                          dataKey="close"
                          stroke="#22d3ee"
                          strokeWidth={2.4}
                          fill="url(#assetArea)"
                          dot={false}
                          isAnimationActive={false}
                        />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-[color:var(--nexus-card-stroke)] bg-white/[0.02]">
                      <p className="font-mono text-[11px] text-[var(--nexus-muted)]">
                        Live OHLC not available yet.
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/10 p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                    Quick analytics
                  </p>
                  <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                    {chartRows.length ? `${chartRows.length} pts` : "—"}
                  </p>
                </div>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  <div className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-white/[0.02] px-3 py-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                      Return
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                      {pct(seriesStats?.retPct ?? null, 2)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-white/[0.02] px-3 py-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                      PnL
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                      {fmtUsd(seriesStats?.pnlUsd ?? null)}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-white/[0.02] px-3 py-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                      Range
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                      {seriesStats ? fmtUsd(seriesStats.hi - seriesStats.lo) : "—"}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-white/[0.02] px-3 py-2">
                    <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                      Max DD
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                      {fmtDrawdownPct(seriesStats?.ddPct ?? null, 2)}
                    </p>
                  </div>
                </div>

              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-5 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Highlights
            </p>
            <div className="mt-3 space-y-3">
              <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(34,211,238,0.18),rgba(34,211,238,0.03))] p-3">
                <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                  Compliance
                </p>
                <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">Clear</p>
              </div>
              <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(0,212,170,0.18),rgba(0,212,170,0.03))] p-3">
                <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                  Allocation
                </p>
                <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                  {allocation.length ? `${allocation[0]?.asset ?? "—"} · top` : "—"}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-[var(--nexus-muted)]">
                  {allocation.length
                    ? `${((allocation[0].value / Math.max(1, allocationTotal)) * 100).toFixed(1)}%`
                    : "—"}
                </p>
              </div>
              <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[linear-gradient(180deg,rgba(245,158,11,0.18),rgba(245,158,11,0.03))] p-3">
                <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                  Freshness
                </p>
                <p className="mt-1 font-mono text-[12px] text-[var(--nexus-text)]">
                  {formatTimeShort(
                    (useReplay ? seriesStats?.lastTs : (health?.ts ?? null)) as number | null,
                  )}
                </p>
                <p className="mt-0.5 font-mono text-[10px] text-[var(--nexus-muted)]">
                  Data-driven
                </p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                Positions
              </p>
              <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                {positions.length} open
              </p>
            </div>

            <div className="mt-3 overflow-hidden rounded-lg border border-[var(--nexus-rule-soft)]">
              <div className="grid grid-cols-12 gap-2 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-surface)]/45 px-3 py-2 font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                <div className="col-span-5">Symbol</div>
                <div className="col-span-2 text-right">Side</div>
                <div className="col-span-2 text-right">Qty</div>
                <div className="col-span-3 text-right">Entry</div>
              </div>
              <div className="max-h-[260px] overflow-auto">
                {positions.length ? (
                  positions.map((p, i) => {
                    const sym =
                      pickString(p, ["symbol", "ticker", "pair", "instrument"]) ??
                      (typeof p === "string" ? p : `pos_${i + 1}`);
                    const side = pickString(p, ["side", "direction", "positionSide"]) ?? "—";
                    const qty = pickNumber(p, ["qty", "quantity", "size", "positionAmt", "amount"]);
                    const entry = pickNumber(p, [
                      "entry",
                      "entry_price",
                      "avgEntryPrice",
                      "entryPrice",
                      "price",
                    ]);
                    return (
                      <div
                        key={`${sym}_${i}`}
                        className="grid grid-cols-12 gap-2 border-b border-[var(--nexus-rule-soft)] px-3 py-2 font-mono text-[11px] text-slate-200 last:border-b-0"
                      >
                        <div className="col-span-5 truncate text-[var(--nexus-text)]">{sym}</div>
                        <div className="col-span-2 text-right text-[var(--nexus-muted)]">
                          {side}
                        </div>
                        <div className="col-span-2 text-right tabular-nums text-[var(--nexus-text)]">
                          {qty == null ? "—" : fmtNum(qty, 6)}
                        </div>
                        <div className="col-span-3 text-right tabular-nums text-[var(--nexus-muted)]">
                          {entry == null ? "—" : fmtUsd(entry)}
                        </div>
                      </div>
                    );
                  })
                ) : (
                  <div className="px-3 py-3 font-mono text-[11px] text-[var(--nexus-muted)]">
                    No open positions reported.
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Agent events
            </p>
            <p className="mt-2 text-[12px] leading-relaxed text-[var(--nexus-muted)]">
              Event tape and agent thoughts live on{" "}
              <a
                href="/console?view=flow"
                className="text-[var(--nexus-glow)] underline-offset-2 hover:underline"
              >
                Live desk
              </a>
              . Backtest timelines stay in{" "}
              <a
                href="/console?view=research"
                className="text-[var(--nexus-glow)] underline-offset-2 hover:underline"
              >
                Research
              </a>
              .
            </p>
          </div>
        </section>

        <section className="grid gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
          <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                Assets / equity trend
              </p>
              <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                {chartRows.length ? `${chartRows.length} pts` : "—"}
              </p>
            </div>
            <div className="mt-3 h-[220px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartRows} margin={{ left: 12, right: 12, top: 6, bottom: 0 }}>
                  <defs>
                    <linearGradient id="nexusAreaTotal" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3B82F6" stopOpacity={0.38} />
                      <stop offset="100%" stopColor="#3B82F6" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="nexusAreaUsdt" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#00D4AA" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#00D4AA" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="rgba(226,232,240,0.06)" vertical={false} />
                  <XAxis
                    dataKey="ts"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    scale="time"
                    tick={{ fill: "rgba(138,149,166,0.9)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    minTickGap={28}
                    tickFormatter={(v) => formatChartTickLabel(Number(v), chartTimeRangeMs)}
                  />
                  <YAxis
                    tick={{ fill: "rgba(138,149,166,0.9)", fontSize: 10 }}
                    tickLine={false}
                    axisLine={false}
                    width={56}
                    tickFormatter={(v) =>
                      `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`
                    }
                  />
                  <Tooltip
                    contentStyle={{
                      background: "rgba(10,13,18,0.92)",
                      border: "1px solid rgba(138,149,166,0.22)",
                      borderRadius: 10,
                      fontFamily:
                        "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                      fontSize: 11,
                    }}
                    formatter={(v: unknown) => fmtUsd(typeof v === "number" ? v : null)}
                    labelFormatter={(l) => formatChartTickLabel(Number(l), chartTimeRangeMs)}
                  />
                  <Area
                    type="monotone"
                    dataKey="totalUsd"
                    stroke="#3B82F6"
                    strokeWidth={2}
                    fill="url(#nexusAreaTotal)"
                    dot={false}
                    isAnimationActive={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="usdt"
                    stroke="#00D4AA"
                    strokeWidth={1.5}
                    fill="url(#nexusAreaUsdt)"
                    dot={false}
                    isAnimationActive={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 font-mono text-[10px] text-[var(--nexus-muted)]">
              Latest: <span className="text-[var(--nexus-text)]">{fmtUsd(totalStable)}</span>{" "}
              <span className="text-[var(--nexus-muted)]">· USDT</span>{" "}
              <span className="text-[var(--nexus-text)]">{fmtUsd(usdt)}</span>
            </p>
          </div>

          <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                Allocation (balances)
              </p>
              <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                {allocation.length ? `${allocation.length} assets` : "—"}
              </p>
            </div>
            <div className="mt-3 grid gap-3 sm:grid-cols-[200px_minmax(0,1fr)]">
              <div className="h-[200px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={allocation}
                      dataKey="value"
                      nameKey="asset"
                      innerRadius={52}
                      outerRadius={82}
                      paddingAngle={2}
                      stroke="rgba(0,0,0,0)"
                      isAnimationActive={false}
                    >
                      {allocation.map((_, idx) => (
                        <Cell key={idx} fill={allocationColors[idx % allocationColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "rgba(10,13,18,0.92)",
                        border: "1px solid rgba(138,149,166,0.22)",
                        borderRadius: 10,
                        fontFamily:
                          "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                        fontSize: 11,
                      }}
                      formatter={(
                        v: unknown,
                        _n,
                        p: { payload?: { asset?: unknown } } | undefined,
                      ) =>
                        `${fmtNum(typeof v === "number" ? v : null, 4)} ${String(p?.payload?.asset ?? "")}`
                      }
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="min-w-0">
                <div className="space-y-2">
                  {allocation.length ? (
                    allocation.map((r, idx) => (
                      <div
                        key={r.asset}
                        className="flex items-center justify-between gap-3 font-mono text-[11px]"
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 rounded-sm"
                            style={{ background: allocationColors[idx % allocationColors.length] }}
                            aria-hidden
                          />
                          <span className="truncate text-[var(--nexus-text)]">{r.asset}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-white/5 ring-1 ring-white/10">
                            <div
                              className="h-full rounded-full"
                              style={{
                                width: `${Math.min(100, Math.max(0, allocationTotal > 0 ? (r.value / allocationTotal) * 100 : 0)).toFixed(1)}%`,
                                background: allocationColors[idx % allocationColors.length],
                              }}
                            />
                          </div>
                          <span className="tabular-nums text-[var(--nexus-muted)]">
                            {allocationTotal > 0
                              ? `${((r.value / allocationTotal) * 100).toFixed(1)}%`
                              : "—"}
                          </span>
                        </div>
                      </div>
                    ))
                  ) : (
                    <p className="font-mono text-[11px] text-[var(--nexus-muted)]">
                      No balances yet.
                    </p>
                  )}
                </div>
              </div>
            </div>
          </div>
        </section>

        <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
            Raw portfolio health
          </p>
          <pre className="mt-2 overflow-auto rounded-lg border border-[var(--nexus-rule-soft)] bg-[var(--nexus-bg)]/40 p-3 text-[11px] text-[var(--nexus-muted)]">
            {JSON.stringify(health ?? {}, null, 2)}
          </pre>
        </section>
      </div>
    </div>
  );
}
