"use client";

import { useMemo, useState } from "react";
import type { TradeRow } from "@/types/backtest";

function fmtTime(ts?: number): string {
  if (ts == null) return "—";
  try {
    return new Date(ts).toISOString().replace("T", " ").slice(0, 19) + "Z";
  } catch {
    return "—";
  }
}

export function BacktestTradesTable({
  trades,
  truncated,
  total,
  returned,
}: {
  trades: TradeRow[];
  truncated?: boolean;
  total?: number;
  returned?: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const canExpand = trades.length > 14;
  const maxH = expanded ? "max-h-[70vh]" : "max-h-[280px]";
  const shown = returned ?? trades.length;
  const totals = total != null ? total : null;
  const summary = useMemo(() => {
    const parts: string[] = [];
    if (totals != null) parts.push(`${shown.toLocaleString()} / ${totals.toLocaleString()} rows`);
    else parts.push(`${shown.toLocaleString()} rows`);
    if (truncated) parts.push("truncated");
    return parts.join(" · ");
  }, [shown, totals, truncated]);

  if (!trades.length) {
    return (
      <p className="font-mono text-[11px] text-[var(--nexus-muted)]">
        No fills in this run (risk veto or no portfolio proposals).
      </p>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] text-[var(--nexus-muted)]">{summary}</p>
        {canExpand ? (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/40 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        ) : null}
      </div>
      {truncated ? (
        <p className="font-mono text-[10px] text-amber-200/90">
          Showing the most recent rows (server limit). Export JSON from the run payload for full
          ledger paths on disk.
        </p>
      ) : null}
      <div
        className={`nexus-scroll overflow-auto rounded-lg border border-[color:var(--nexus-card-stroke)] ${maxH}`}
      >
        <table className="w-full border-collapse font-mono text-[10px]">
          <thead className="sticky top-0 bg-[var(--nexus-panel)] text-left text-[var(--nexus-muted)]">
            <tr className="border-b border-[var(--nexus-rule-soft)]">
              <th className="px-2 py-2">Step</th>
              <th className="px-2 py-2">Time</th>
              <th className="px-2 py-2">Side</th>
              <th className="px-2 py-2 text-right">Qty</th>
              <th className="px-2 py-2 text-right">Price</th>
              <th className="px-2 py-2 text-right">Cash</th>
              <th className="px-2 py-2 text-right">Base</th>
            </tr>
          </thead>
          <tbody>
            {trades.map((t, i) => (
              <tr
                key={`${t.step}-${i}`}
                className="border-b border-[var(--nexus-rule-soft)] hover:bg-[var(--nexus-glow)]/[0.04]"
              >
                <td className="px-2 py-1.5 text-[var(--nexus-muted)]">{t.step}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-[var(--nexus-muted)]">
                  {fmtTime(t.ts_ms)}
                </td>
                <td
                  className={
                    t.side === "buy"
                      ? "text-[var(--nexus-success)]"
                      : t.side === "sell"
                        ? "text-[var(--nexus-danger)]"
                        : ""
                  }
                >
                  {t.side}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {Number(t.qty).toLocaleString(undefined, { maximumFractionDigits: 6 })}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums">
                  {Number(t.price).toLocaleString(undefined, { maximumFractionDigits: 4 })}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[var(--nexus-muted)]">
                  {t.cash != null
                    ? Number(t.cash).toLocaleString(undefined, { maximumFractionDigits: 2 })
                    : "—"}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[var(--nexus-muted)]">
                  {t.qty_base != null
                    ? Number(t.qty_base).toLocaleString(undefined, { maximumFractionDigits: 6 })
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
