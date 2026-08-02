"use client";

import { useMemo } from "react";
import type { SummaryPayload, TradeRow } from "@/types/backtest";

type QualityGate = {
  key: string;
  label: string;
  passed: boolean | null;
  detail: string;
};

type AttributionRow = {
  symbol: string;
  pnl: number;
  trades: number;
  wins: number;
  winRate: number;
  contributionPct: number;
};

function tradePnl(t: TradeRow): number {
  const raw = t.pnl_usd ?? t.pnl;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : 0;
}

function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : null;
}

function gatePassed(obj: unknown): boolean | null {
  const r = asRecord(obj);
  if (!r || typeof r.passed !== "boolean") return null;
  return r.passed;
}

function gateWarning(obj: unknown): string {
  const r = asRecord(obj);
  const w = r?.warning;
  return typeof w === "string" && w.trim() ? w.trim() : "";
}

function buildGates(qr: Record<string, unknown> | undefined): {
  overall: boolean | null;
  warnings: string[];
  gates: QualityGate[];
} {
  if (!qr) return { overall: null, warnings: [], gates: [] };
  const overall = typeof qr.overall_passed === "boolean" ? qr.overall_passed : null;
  const warnings = Array.isArray(qr.warnings)
    ? qr.warnings.filter((w): w is string => typeof w === "string" && w.trim().length > 0)
    : [];

  const sample = asRecord(qr.sample_size);
  const pl = asRecord(qr.profit_loss_ratio);
  const exits = asRecord(qr.exit_reasons);
  const regime = asRecord(qr.regime_coverage);
  const fwd = asRecord(qr.forward_validation);

  const gates: QualityGate[] = [
    {
      key: "sample",
      label: "Sample size",
      passed: gatePassed(sample),
      detail:
        sample && typeof sample.trade_count === "number"
          ? `${sample.trade_count} trades · ${sample.total_bars ?? "—"} bars`
          : gateWarning(sample) || "—",
    },
    {
      key: "pf",
      label: "Profit factor",
      passed: gatePassed(pl),
      detail:
        pl && typeof pl.profit_factor === "number"
          ? `PF ${Number(pl.profit_factor).toFixed(2)}${
              typeof pl.threshold === "number" ? ` (min ${pl.threshold})` : ""
            }`
          : gateWarning(pl) || "—",
    },
    {
      key: "exits",
      label: "Exit mix",
      passed: gatePassed(exits),
      detail: gateWarning(exits) || "Distribution looks healthy",
    },
    {
      key: "regime",
      label: "Regime coverage",
      passed: gatePassed(regime),
      detail: Array.isArray(regime?.regimes_covered)
        ? (regime!.regimes_covered as unknown[]).map(String).join(", ") || "—"
        : gateWarning(regime) || "—",
    },
  ];

  if (fwd) {
    gates.push({
      key: "fwd",
      label: "Forward validation",
      passed: gatePassed(fwd),
      detail: gateWarning(fwd) || "In-sample / out-of-sample split available",
    });
  }

  return { overall, warnings, gates: gates.filter((g) => g.passed != null || g.detail !== "—") };
}

function buildAttribution(trades: TradeRow[]): AttributionRow[] {
  const agg = new Map<string, { pnl: number; trades: number; wins: number }>();
  for (const t of trades) {
    const sym = (t.symbol || "?").trim() || "?";
    const pnl = tradePnl(t);
    const cur = agg.get(sym) ?? { pnl: 0, trades: 0, wins: 0 };
    cur.pnl += pnl;
    cur.trades += 1;
    if (pnl > 0) cur.wins += 1;
    agg.set(sym, cur);
  }
  const totalAbs = Math.abs([...agg.values()].reduce((s, v) => s + v.pnl, 0)) || 1;
  return [...agg.entries()]
    .map(([symbol, v]) => ({
      symbol,
      pnl: v.pnl,
      trades: v.trades,
      wins: v.wins,
      winRate: (100 * v.wins) / Math.max(1, v.trades),
      contributionPct: (100 * v.pnl) / totalAbs,
    }))
    .sort((a, b) => b.pnl - a.pnl);
}

function buildExitDist(
  qr: Record<string, unknown> | undefined,
  trades: TradeRow[],
): { reason: string; count: number; pct: number }[] {
  const exits = asRecord(qr?.exit_reasons);
  const dist = asRecord(exits?.distribution);
  const pctDist = asRecord(exits?.pct_distribution);

  if (dist && Object.keys(dist).length) {
    const rows = Object.entries(dist).map(([reason, count]) => {
      const n = typeof count === "number" ? count : Number(count) || 0;
      const pctRaw = pctDist?.[reason];
      const pct = typeof pctRaw === "number" ? pctRaw : 0;
      return { reason, count: n, pct };
    });
    rows.sort((a, b) => b.count - a.count);
    return rows;
  }

  const counter = new Map<string, number>();
  for (const t of trades) {
    const reason = (t.exit_reason || "").trim();
    if (!reason) continue;
    counter.set(reason, (counter.get(reason) ?? 0) + 1);
  }
  const total = [...counter.values()].reduce((s, n) => s + n, 0) || 1;
  return [...counter.entries()]
    .map(([reason, count]) => ({ reason, count, pct: (100 * count) / total }))
    .sort((a, b) => b.count - a.count);
}

function fmtUsd(n: number): string {
  const sign = n > 0 ? "+" : "";
  return `${sign}$${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function BacktestReportInsights({
  summary,
  trades,
  compact = false,
}: {
  summary: SummaryPayload | null;
  trades: TradeRow[];
  compact?: boolean;
}) {
  const qr = summary?.quality_report as Record<string, unknown> | undefined;
  const { overall, warnings, gates } = useMemo(() => buildGates(qr), [qr]);
  const attribution = useMemo(() => buildAttribution(trades), [trades]);
  const exits = useMemo(() => buildExitDist(qr, trades), [qr, trades]);

  if (!gates.length && !attribution.length && !exits.length) return null;

  const card = compact
    ? "rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-2.5"
    : "rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4";
  const h3 = compact
    ? "font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]"
    : "font-mono text-[11px] uppercase tracking-widest text-[var(--nexus-muted)]";
  const body = compact ? "text-[10px]" : "text-[11px]";

  return (
    <div className={compact ? "space-y-2" : "space-y-4"}>
      {gates.length ? (
        <div className={card}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className={h3}>Quality gates</h3>
            {overall != null ? (
              <span
                className={`font-mono text-[10px] uppercase tracking-wider ${
                  overall ? "text-[var(--nexus-success)]" : "text-amber-300"
                }`}
              >
                {overall ? "Passed" : "Review"}
              </span>
            ) : null}
          </div>
          <p className={`text-[var(--nexus-muted)] ${compact ? "mt-1 text-[9px]" : "mt-1 text-[10px]"}`}>
            Statistical checks from the engine quality report — not live book health.
          </p>
          <div
            className={`mt-2 grid gap-1.5 ${compact ? "sm:grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-3"}`}
          >
            {gates.map((g) => (
              <div
                key={g.key}
                className="rounded-md border border-[color:var(--nexus-rule-soft)] bg-[var(--nexus-bg)]/30 px-2.5 py-2"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className={`font-mono ${body} text-[var(--nexus-text)]`}>{g.label}</span>
                  <span
                    className={`font-mono text-[9px] uppercase ${
                      g.passed === true
                        ? "text-[var(--nexus-success)]"
                        : g.passed === false
                          ? "text-amber-300"
                          : "text-[var(--nexus-muted)]"
                    }`}
                  >
                    {g.passed === true ? "ok" : g.passed === false ? "warn" : "—"}
                  </span>
                </div>
                <p className={`mt-1 font-mono text-[var(--nexus-muted)] ${compact ? "text-[9px]" : "text-[10px]"}`}>
                  {g.detail}
                </p>
              </div>
            ))}
          </div>
          {warnings.length ? (
            <ul className={`mt-2 space-y-1 font-mono text-amber-200/90 ${compact ? "text-[9px]" : "text-[10px]"}`}>
              {warnings.slice(0, 4).map((w) => (
                <li key={w}>· {w}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      <div className={compact ? "grid gap-2 lg:grid-cols-2" : "grid gap-4 lg:grid-cols-2"}>
        {attribution.length ? (
          <div className={card}>
            <h3 className={h3}>Per-symbol attribution</h3>
            <p className={`text-[var(--nexus-muted)] ${compact ? "mt-1 mb-1.5 text-[9px]" : "mt-1 mb-2 text-[10px]"}`}>
              Realized PnL contribution by symbol from filled trades.
            </p>
            <div className="overflow-hidden rounded-md border border-[color:var(--nexus-rule-soft)]">
              <div
                className={`grid grid-cols-12 gap-1 border-b border-[color:var(--nexus-rule-soft)] bg-[var(--nexus-surface)]/40 px-2 py-1.5 font-mono uppercase tracking-wider text-[var(--nexus-muted)] ${compact ? "text-[8px]" : "text-[9px]"}`}
              >
                <div className="col-span-4">Symbol</div>
                <div className="col-span-3 text-right">PnL</div>
                <div className="col-span-2 text-right">Trades</div>
                <div className="col-span-3 text-right">Win%</div>
              </div>
              {attribution.slice(0, 8).map((r) => (
                <div
                  key={r.symbol}
                  className={`grid grid-cols-12 gap-1 border-b border-[color:var(--nexus-rule-soft)] px-2 py-1.5 font-mono last:border-b-0 ${body}`}
                >
                  <div className="col-span-4 truncate text-[var(--nexus-text)]">{r.symbol}</div>
                  <div
                    className={`col-span-3 text-right tabular-nums ${
                      r.pnl >= 0 ? "text-[var(--nexus-success)]" : "text-[var(--nexus-danger)]"
                    }`}
                  >
                    {fmtUsd(r.pnl)}
                  </div>
                  <div className="col-span-2 text-right tabular-nums text-[var(--nexus-muted)]">
                    {r.trades}
                  </div>
                  <div className="col-span-3 text-right tabular-nums text-[var(--nexus-text)]">
                    {r.winRate.toFixed(0)}%
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {exits.length ? (
          <div className={card}>
            <h3 className={h3}>Exit reasons</h3>
            <p className={`text-[var(--nexus-muted)] ${compact ? "mt-1 mb-1.5 text-[9px]" : "mt-1 mb-2 text-[10px]"}`}>
              How positions closed — concentration can flag fragile edges.
            </p>
            <ul className="space-y-1.5">
              {exits.slice(0, 8).map((e) => (
                <li key={e.reason} className="font-mono">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={`truncate text-[var(--nexus-text)] ${body}`}>{e.reason}</span>
                    <span className={`shrink-0 tabular-nums text-[var(--nexus-muted)] ${compact ? "text-[9px]" : "text-[10px]"}`}>
                      {e.count} · {e.pct.toFixed(0)}%
                    </span>
                  </div>
                  <div className="mt-1 h-1 overflow-hidden rounded-full bg-white/5">
                    <div
                      className="h-full rounded-full bg-[var(--nexus-glow)]/70"
                      style={{ width: `${Math.min(100, Math.max(2, e.pct))}%` }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </div>
  );
}
