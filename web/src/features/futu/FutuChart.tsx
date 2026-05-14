"use client";

import { useCallback, useMemo, useRef, useEffect } from "react";
import {
  ColorType,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
} from "lightweight-charts";

export interface FutuBar {
  ts: number; // epoch ms (normalized upstream)
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FutuChartProps {
  bars: FutuBar[];
  symbol: string;
  /** Affects how `time` is encoded for the library (daily vs intraday). */
  interval?: "1d" | "1w" | "1h" | string;
  width?: number;
  height?: number;
}

function utcDayString(tsMs: number): string {
  const d = new Date(tsMs);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, "0");
  const day = String(d.getUTCDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/**
 * FutuChart — Lightweight candlestick chart for Futu stock data.
 * Chart is created once; bars update via setData (avoids full teardown on each fetch).
 */
export function FutuChart({ bars, symbol, interval = "1d", width, height = 420 }: FutuChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const { candleData, volumeData } = useMemo(() => {
    const candles: CandlestickData[] = [];
    const vols: HistogramData[] = [];
    const useBusinessDay = interval === "1d" || interval === "1w";

    for (const b of bars) {
      const time: Time = useBusinessDay
        ? (utcDayString(b.ts) as Time)
        : (Math.floor(b.ts / 1000) as Time);
      candles.push({
        time,
        open: b.open,
        high: b.high,
        low: b.low,
        close: b.close,
      });
      vols.push({
        time,
        value: b.volume,
        color:
          b.close >= b.open ? "rgba(60, 255, 170, 0.35)" : "rgba(242, 92, 84, 0.35)",
      });
    }

    return { candleData: candles, volumeData: vols };
  }, [bars, interval]);

  const applyData = useCallback(() => {
    const chart = chartRef.current;
    const candleSeries = candleSeriesRef.current;
    const volSeries = volumeSeriesRef.current;
    if (!chart || !candleSeries || !volSeries) return;
    candleSeries.setData(candleData);
    volSeries.setData(volumeData);
    chart.timeScale().fitContent();
  }, [candleData, volumeData]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      width: width ?? el.clientWidth,
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "rgba(138, 149, 166, 0.7)",
        fontSize: 10,
        fontFamily: "ui-monospace, monospace",
      },
      grid: {
        vertLines: { color: "rgba(138, 149, 166, 0.06)" },
        horzLines: { color: "rgba(138, 149, 166, 0.06)" },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: "rgba(138, 149, 166, 0.25)",
          width: 1,
          style: 2,
          labelBackgroundColor: "rgba(10, 13, 18, 0.9)",
        },
        horzLine: {
          color: "rgba(138, 149, 166, 0.25)",
          width: 1,
          style: 2,
          labelBackgroundColor: "rgba(10, 13, 18, 0.9)",
        },
      },
      rightPriceScale: {
        borderColor: "rgba(138, 149, 166, 0.1)",
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "rgba(138, 149, 166, 0.1)",
        timeVisible: interval === "1h",
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: "rgba(60, 255, 170, 0.85)",
      downColor: "rgba(242, 92, 84, 0.85)",
      borderUpColor: "rgba(60, 255, 170, 0.9)",
      borderDownColor: "rgba(242, 92, 84, 0.9)",
      wickUpColor: "rgba(60, 255, 170, 0.75)",
      wickDownColor: "rgba(242, 92, 84, 0.75)",
    });

    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volSeries;

    const ro = new ResizeObserver(() => {
      const w = width ?? el.clientWidth;
      if (w > 0) chart.applyOptions({ width: w });
    });
    ro.observe(el);

    candleSeries.setData(candleData);
    volSeries.setData(volumeData);
    chart.timeScale().fitContent();

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- init once per mount / size mode
  }, [height, width, interval]);

  useEffect(() => {
    applyData();
  }, [applyData, symbol]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl overflow-hidden"
      style={{ height }}
    />
  );
}
