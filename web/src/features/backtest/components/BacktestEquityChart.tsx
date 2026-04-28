"use client";

import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  Scatter,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { EquityPoint, TradeRow } from "@/types/backtest";

function formatTime(tsMs: number): string {
  try {
    return new Date(tsMs).toISOString().replace("T", " ").slice(0, 19) + "Z";
  } catch {
    return String(tsMs);
  }
}

type Row = EquityPoint & { label: string };

type FillMarkerShapeProps = {
  cx?: number;
  cy?: number;
  payload?: {
    side?: "buy" | "sell";
  };
};

export function BacktestEquityChart({
  points,
  initialCash,
  trades = [],
}: {
  points: EquityPoint[];
  initialCash: number;
  trades?: TradeRow[];
}) {
  if (!points.length) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] font-mono text-[11px] text-[var(--nexus-muted)]">
        No equity points (run may have failed or data unavailable).
      </div>
    );
  }

  const data: Row[] = points.map((p) => ({
    ...p,
    label: `Bar ${p.step + 1}`,
  }));

  const equityByStep = new Map<number, number>();
  for (const p of points) equityByStep.set(p.step, p.equity);

  const markers = (trades ?? [])
    .filter((t) => t && (t.side === "buy" || t.side === "sell") && typeof t.step === "number")
    .map((t) => {
      const eq = equityByStep.get(t.step);
      if (typeof eq !== "number") return null;
      return {
        step: t.step,
        equity: eq,
        side: t.side,
        ts_ms: t.ts_ms,
        qty: t.qty,
        price: t.price,
      };
    })
    .filter((m): m is NonNullable<typeof m> => Boolean(m));

  return (
    <div className="h-[320px] w-full min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke="rgba(138,149,166,0.12)" strokeDasharray="3 3" />
          <XAxis
            dataKey="step"
            tick={{ fill: "var(--nexus-muted)", fontSize: 10 }}
            tickLine={false}
            tickFormatter={(v: number) => String(v + 1)}
          />
          <YAxis
            domain={["auto", "auto"]}
            tick={{ fill: "var(--nexus-muted)", fontSize: 10 }}
            tickFormatter={(v: number) =>
              v >= 1e6
                ? `${(v / 1e6).toFixed(2)}M`
                : v >= 1e3
                  ? `${(v / 1e3).toFixed(1)}k`
                  : String(v)
            }
            width={56}
          />
          <Tooltip
            contentStyle={{
              background: "var(--nexus-panel)",
              border: "1px solid var(--nexus-card-stroke)",
              borderRadius: 8,
              fontSize: 11,
              fontFamily: "ui-monospace, monospace",
            }}
            labelFormatter={(_, payload) => {
              const row = payload?.[0]?.payload as Row | undefined;
              if (!row) return "";
              return `${row.label} · ${formatTime(row.ts_ms)}`;
            }}
            formatter={(value: number | string, name: string) => {
              if (name === "equity") {
                return [
                  Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 }),
                  "Equity (sim)",
                ];
              }
              return [value, name];
            }}
          />
          <ReferenceLine
            y={initialCash}
            stroke="rgba(0, 212, 170, 0.35)"
            strokeDasharray="4 4"
            label={{
              value: "Initial",
              fill: "var(--nexus-muted)",
              fontSize: 10,
            }}
          />
          <Line
            type="monotone"
            dataKey="equity"
            stroke="var(--nexus-glow)"
            dot={false}
            strokeWidth={2}
            name="equity"
          />
          {markers.length ? (
            <Scatter
              data={markers}
              xAxisId={0}
              yAxisId={0}
              name="fills"
              shape={(props: unknown) => {
                const { cx, cy, payload } = (props ?? {}) as FillMarkerShapeProps;
                if (typeof cx !== "number" || typeof cy !== "number") return <g />;
                const side = payload?.side;
                const size = 6.5;
                const fill =
                  side === "buy"
                    ? "rgba(60, 255, 170, 0.95)"
                    : side === "sell"
                      ? "rgba(242, 92, 84, 0.95)"
                      : "rgba(138,149,166,0.85)";
                const stroke = "rgba(10, 13, 18, 0.85)";
                const up = side === "buy";
                const pts = up
                  ? `${cx},${cy - size} ${cx - size},${cy + size} ${cx + size},${cy + size}`
                  : `${cx},${cy + size} ${cx - size},${cy - size} ${cx + size},${cy - size}`;
                return (
                  <g>
                    <polygon points={pts} fill={fill} stroke={stroke} strokeWidth={1} />
                  </g>
                );
              }}
            />
          ) : null}
          <Brush
            dataKey="step"
            height={22}
            stroke="var(--nexus-card-stroke)"
            fill="rgba(10, 13, 18, 0.85)"
            travellerWidth={8}
            tickFormatter={(v: number) => String(v + 1)}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
