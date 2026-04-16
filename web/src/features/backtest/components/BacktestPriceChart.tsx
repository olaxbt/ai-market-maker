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
        .filter((b) => typeof b.ts_ms === "number")
        .map((b) => ({
          time: toUtcTimestamp(b.ts_ms),
          open: Number(b.open),
          high: Number(b.high),
          low: Number(b.low),
          close: Number(b.close),
        })),
    [bars],
  );

  const markers = useMemo((): SeriesMarker<UTCTimestamp>[] => {
    if (!trades?.length || !bars.length) return [];
    const tsByStep = new Map<number, number>();
    for (const b of bars) tsByStep.set(b.step, b.ts_ms);
    // Aggregate fills per bar step so the chart doesn't stack 2-5 arrows on the same candle.
    // (Multiple fills per step are valid; we just render one marker with count + avg price.)
    const key = (step: number, side: string) => `${step}:${side}`;
    const agg = new Map<
      string,
      { step: number; side: "buy" | "sell"; ts: number; qty: number; notional: number; fills: number }
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
    return rows.map((r) => {
      const avg = r.qty !== 0 ? r.notional / r.qty : NaN;
      const avgLabel = Number.isFinite(avg)
        ? avg.toLocaleString(undefined, { maximumFractionDigits: 2 })
        : "—";
      const qtyLabel = r.qty.toLocaleString(undefined, { maximumFractionDigits: 6 });
      const fillSuffix = r.fills > 1 ? ` (${r.fills})` : "";
      return {
        time: toUtcTimestamp(r.ts),
        position: r.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
        color: r.side === "buy" ? "rgba(0, 212, 170, 0.95)" : "rgba(242, 92, 84, 0.95)",
        shape: r.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
        text: `${r.side.toUpperCase()} ${qtyLabel} @ ${avgLabel}${fillSuffix}`,
      };
    });
  }, [trades, bars]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    if (chartRef.current) return;

    const chart = createChart(host, {
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

    series.setData(candleData);
    if (markers.length) series.setMarkers(markers);
    chart.timeScale().fitContent();

    chartRef.current = chart;
    candleRef.current = series;

    const ro = new ResizeObserver(() => {
      if (!hostRef.current || !chartRef.current) return;
      chartRef.current.applyOptions({ width: hostRef.current.clientWidth });
    });
    ro.observe(host);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [height]);

  useEffect(() => {
    const series = candleRef.current;
    if (!series) return;
    series.setData(candleData);
    series.setMarkers(markers);
  }, [candleData, markers]);

  if (!bars.length) {
    return (
      <div className="flex h-[280px] items-center justify-center rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] font-mono text-[11px] text-[var(--nexus-muted)]">
        No price bars available for this run yet.
      </div>
    );
  }

  return <div ref={hostRef} className="w-full min-w-0" style={{ height }} />;
}

