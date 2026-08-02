"use client";

import { useEffect, useMemo, useRef } from "react";
import type { IChartApi, ISeriesApi, SeriesMarker, UTCTimestamp } from "lightweight-charts";
import { createChart } from "lightweight-charts";
import type { OhlcvBar, TradeRow } from "@/types/backtest";

function toUtcTimestamp(tsMs: number): UTCTimestamp {
  return Math.floor(tsMs / 1000) as UTCTimestamp;
}

export function BacktestPriceChart({
  bars,
  trades,
  height = 320,
}: {
  bars: OhlcvBar[];
  trades?: TradeRow[];
  height?: number;
}) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const candleData = useMemo(
    () =>
      bars
        .map((b, idx) => {
          const anyB = b as OhlcvBar & {
            ts?: number;
            o?: number;
            h?: number;
            l?: number;
            c?: number;
          };
          const tsMs =
            typeof anyB.ts_ms === "number"
              ? anyB.ts_ms
              : typeof anyB.ts === "number"
                ? anyB.ts
                : NaN;
          const open = Number(anyB.open ?? anyB.o);
          const high = Number(anyB.high ?? anyB.h);
          const low = Number(anyB.low ?? anyB.l);
          const close = Number(anyB.close ?? anyB.c);
          if (!Number.isFinite(tsMs) || ![open, high, low, close].every(Number.isFinite)) {
            return null;
          }
          return {
            time: toUtcTimestamp(tsMs),
            open,
            high,
            low,
            close,
            _idx: idx,
          };
        })
        .filter((row): row is NonNullable<typeof row> => row != null)
        .map(({ _idx: _i, ...row }) => row)
        // lightweight-charts requires ascending unique times
        .sort((a, b) => Number(a.time) - Number(b.time))
        .filter((row, i, arr) => i === 0 || Number(row.time) !== Number(arr[i - 1].time)),
    [bars],
  );

  const candleTimes = useMemo(() => new Set(candleData.map((c) => Number(c.time))), [candleData]);

  const markers = useMemo((): SeriesMarker<UTCTimestamp>[] => {
    if (!trades?.length || !bars.length || !candleTimes.size) return [];
    const tsByStep = new Map<number, number>();
    for (const [idx, b] of bars.entries()) {
      const anyB = b as OhlcvBar & { ts?: number };
      const ts =
        typeof anyB.ts_ms === "number" ? anyB.ts_ms : typeof anyB.ts === "number" ? anyB.ts : null;
      const step = typeof anyB.step === "number" ? anyB.step : idx;
      if (typeof ts === "number") tsByStep.set(step, ts);
    }
    const key = (step: number, side: string) => `${step}:${side}`;
    const agg = new Map<
      string,
      {
        step: number;
        side: "buy" | "sell";
        ts: number;
        qty: number;
        notional: number;
        fills: number;
      }
    >();
    for (const t of trades) {
      const side = t.side === "buy" || t.side === "sell" ? t.side : null;
      if (!side || typeof t.step !== "number") continue;
      const ts = t.ts_ms ?? tsByStep.get(t.step);
      if (typeof ts !== "number") continue;
      const k = key(t.step, side);
      const qty = Number(t.qty);
      const price = Number(t.price);
      const prev = agg.get(k);
      const next = prev ?? { step: t.step, side, ts, qty: 0, notional: 0, fills: 0 };
      next.ts = ts;
      if (Number.isFinite(qty)) next.qty += qty;
      if (Number.isFinite(qty) && Number.isFinite(price)) next.notional += qty * price;
      next.fills += 1;
      agg.set(k, next);
    }
    const rows = Array.from(agg.values()).sort((a, b) => a.ts - b.ts);
    return rows
      .map((r) => {
        const time = toUtcTimestamp(r.ts);
        if (!candleTimes.has(Number(time))) return null;
        const avg = r.qty !== 0 ? r.notional / r.qty : NaN;
        const avgLabel = Number.isFinite(avg)
          ? avg.toLocaleString(undefined, { maximumFractionDigits: 2 })
          : "—";
        const qtyLabel = r.qty.toLocaleString(undefined, { maximumFractionDigits: 6 });
        const fillSuffix = r.fills > 1 ? ` (${r.fills})` : "";
        return {
          time,
          position: r.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
          color: r.side === "buy" ? "rgba(0, 212, 170, 0.95)" : "rgba(242, 92, 84, 0.95)",
          shape: r.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: `${r.side.toUpperCase()} ${qtyLabel} @ ${avgLabel}${fillSuffix}`,
        };
      })
      .filter((m): m is NonNullable<typeof m> => m != null);
  }, [trades, bars, candleTimes]);

  // Keep chart host mounted while bars load async
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    if (!candleData.length) {
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        candleRef.current = null;
      }
      return;
    }

    if (!chartRef.current) {
      const chart = createChart(host, {
        width: Math.max(host.clientWidth || 0, 1),
        height,
        layout: {
          background: { color: "transparent" },
          textColor: "rgba(138,149,166,0.92)",
          fontFamily: "ui-monospace, monospace",
        },
        grid: {
          vertLines: { color: "rgba(138,149,166,0.08)" },
          horzLines: { color: "rgba(138,149,166,0.08)" },
        },
        rightPriceScale: { borderColor: "rgba(138,149,166,0.18)" },
        timeScale: { borderColor: "rgba(138,149,166,0.18)" },
        crosshair: {
          vertLine: { color: "rgba(0, 212, 170, 0.18)" },
          horzLine: { color: "rgba(0, 212, 170, 0.18)" },
        },
      });

      const series = chart.addCandlestickSeries({
        upColor: "rgba(0, 212, 170, 0.75)",
        downColor: "rgba(242, 92, 84, 0.75)",
        borderUpColor: "rgba(0, 212, 170, 0.85)",
        borderDownColor: "rgba(242, 92, 84, 0.85)",
        wickUpColor: "rgba(0, 212, 170, 0.85)",
        wickDownColor: "rgba(242, 92, 84, 0.85)",
      });

      chartRef.current = chart;
      candleRef.current = series;

      const ro = new ResizeObserver(() => {
        if (!hostRef.current || !chartRef.current) return;
        chartRef.current.applyOptions({ width: Math.max(hostRef.current.clientWidth || 0, 1) });
      });
      ro.observe(host);

      return () => {
        ro.disconnect();
        chart.remove();
        chartRef.current = null;
        candleRef.current = null;
      };
    }

    chartRef.current.applyOptions({ height });
  }, [candleData.length, height]);

  useEffect(() => {
    const series = candleRef.current;
    const chart = chartRef.current;
    if (!series || !chart || !candleData.length) return;
    try {
      series.setData(candleData);
      series.setMarkers(markers);
      chart.timeScale().fitContent();
    } catch {
      // Ignore transient lightweight-charts validation errors while data settles.
    }
  }, [candleData, markers]);

  return (
    <div className="relative w-full min-w-0" style={{ height }}>
      <div ref={hostRef} className="h-full w-full min-w-0" />
      {!bars.length ? (
        <div className="absolute inset-0 flex items-center justify-center rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] font-mono text-[11px] text-[var(--nexus-muted)]">
          No price bars available for this run yet.
        </div>
      ) : !candleData.length ? (
        <div className="absolute inset-0 flex items-center justify-center rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] font-mono text-[11px] text-[var(--nexus-muted)]">
          Price bars could not be parsed for this run.
        </div>
      ) : null}
    </div>
  );
}
