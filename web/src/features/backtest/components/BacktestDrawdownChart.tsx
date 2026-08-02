"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint } from "@/types/backtest";

export function BacktestDrawdownChart({
  points,
  height = 180,
}: {
  points: EquityPoint[];
  height?: number;
}) {
  const rows = (() => {
    let peak = -Infinity;
    return points.map((p, idx) => {
      const eq = Number(p.equity);
      if (Number.isFinite(eq) && eq > peak) peak = eq;
      const ddPct =
        Number.isFinite(eq) && peak > 0 && Number.isFinite(peak)
          ? Math.max(0, ((peak - eq) / peak) * 100)
          : 0;
      const step = typeof p.step === "number" ? p.step : idx;
      return { step, ddPct, label: `Bar ${step + 1}` };
    });
  })();

  if (!rows.length) {
    return (
      <div
        className="flex items-center justify-center rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] font-mono text-[11px] text-[var(--nexus-muted)]"
        style={{ height }}
      >
        No drawdown series yet.
      </div>
    );
  }

  return (
    <div className="w-full min-w-0" style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id="ddFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="rgba(248,113,113,0.45)" />
              <stop offset="100%" stopColor="rgba(248,113,113,0.02)" />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="rgba(138,149,166,0.12)" strokeDasharray="3 3" />
          <XAxis
            dataKey="step"
            tick={{ fill: "var(--nexus-muted)", fontSize: 10 }}
            tickLine={false}
            tickFormatter={(v: number) => String(v + 1)}
          />
          <YAxis
            domain={[0, "auto"]}
            tick={{ fill: "var(--nexus-muted)", fontSize: 10 }}
            tickFormatter={(v: number) => `${v.toFixed(1)}%`}
            width={48}
            reversed
          />
          <Tooltip
            contentStyle={{
              background: "var(--nexus-panel)",
              border: "1px solid var(--nexus-card-stroke)",
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "ui-monospace, monospace",
            }}
            formatter={(value: number) => [`${Number(value).toFixed(2)}%`, "Drawdown"]}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as { label?: string } | undefined;
              return row?.label ?? "";
            }}
          />
          <Area
            type="monotone"
            dataKey="ddPct"
            stroke="rgba(248,113,113,0.9)"
            fill="url(#ddFill)"
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
