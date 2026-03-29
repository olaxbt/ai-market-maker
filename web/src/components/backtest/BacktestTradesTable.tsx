"use client";

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
}: {
  trades: TradeRow[];
  truncated?: boolean;
}) {
  if (!trades.length) {
    return (
      <p className="font-mono text-[11px] text-[var(--nexus-muted)]">
        No fills in this run (risk veto or no portfolio proposals).
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {truncated ? (
        <p className="font-mono text-[10px] text-amber-200/90">
          Showing the most recent rows (server limit). Export JSON from the run payload for full ledger paths on disk.
        </p>
      ) : null}
      <div className="nexus-scroll max-h-[320px] overflow-auto rounded-lg border border-[color:var(--nexus-card-stroke)]">
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
                <td className="whitespace-nowrap px-2 py-1.5 text-[var(--nexus-muted)]">{fmtTime(t.ts_ms)}</td>
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
                <td className="px-2 py-1.5 text-right tabular-nums">{Number(t.qty).toLocaleString(undefined, { maximumFractionDigits: 6 })}</td>
                <td className="px-2 py-1.5 text-right tabular-nums">{Number(t.price).toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[var(--nexus-muted)]">
                  {t.cash != null ? Number(t.cash).toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—"}
                </td>
                <td className="px-2 py-1.5 text-right tabular-nums text-[var(--nexus-muted)]">
                  {t.qty_base != null ? Number(t.qty_base).toLocaleString(undefined, { maximumFractionDigits: 6 }) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
