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
    return trades
      .filter((t) => (t.side === "buy" || t.side === "sell") && typeof t.step === "number")
      .map((t) => {
        const ts = t.ts_ms ?? tsByStep.get(t.step);
        if (typeof ts !== "number") return null;
        return {
          time: toUtcTimestamp(ts),
          position: t.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
          color: t.side === "buy" ? "rgba(0, 212, 170, 0.95)" : "rgba(242, 92, 84, 0.95)",
          shape: t.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
          text: `${t.side.toUpperCase()} ${Number(t.price).toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
        };
      })
      .filter((m): m is NonNullable<typeof m> => Boolean(m));
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

