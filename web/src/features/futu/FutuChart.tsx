"use client";

import { useCallback, useMemo, useRef, useEffect } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi, type CandlestickData, type HistogramData, type Time } from "lightweight-charts";

export interface FutuBar {
  ts: number;    // epoch ms
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface FutuChartProps {
  bars: FutuBar[];
  symbol: string;
  width?: number;
  height?: number;
}

/**
 * FutuChart — Lightweight candlestick chart for Futu stock data.
 *
 * Uses lightweight-charts (TradingView) for professional-grade rendering.
 * Already a dependency in web/package.json.
 */
export function FutuChart({ bars, symbol, width, height = 420 }: FutuChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  // Convert bars to lightweight-charts format
  const { candleData, volumeData } = useMemo(() => {
    const candles: CandlestickData[] = [];
    const vols: HistogramData[] = [];

    for (const b of bars) {
      // lightweight-charts uses seconds for Time
      const time = Math.floor(b.ts / 1000) as Time;
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
        color: b.close >= b.open
          ? "rgba(60, 255, 170, 0.35)"
          : "rgba(242, 92, 84, 0.35)",
      });
    }

    return { candleData: candles, volumeData: vols };
  }, [bars]);

  useEffect(() => {
    if (!containerRef.current) return;

    // Create chart
    const chart = createChart(containerRef.current, {
      width: width ?? containerRef.current.clientWidth,
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
        timeVisible: true,
        secondsVisible: false,
      },
      handleScroll: true,
      handleScale: true,
    });

    // Candlestick series
    const candleSeries = chart.addCandlestickSeries({
      upColor: "rgba(60, 255, 170, 0.85)",
      downColor: "rgba(242, 92, 84, 0.85)",
      borderUpColor: "rgba(60, 255, 170, 0.9)",
      borderDownColor: "rgba(242, 92, 84, 0.9)",
      wickUpColor: "rgba(60, 255, 170, 0.75)",
      wickDownColor: "rgba(242, 92, 84, 0.75)",
    });
    candleSeries.setData(candleData);

    // Volume histogram
    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volSeries.setData(volumeData);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volSeries;

    // Fit content
    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [candleData, volumeData, width, height]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl overflow-hidden"
      style={{ height }}
    />
  );
}
