"use client";

import { useMemo, useEffect, useRef } from "react";
import { ColorType, createChart, type IChartApi, type ISeriesApi, type CandlestickData, type HistogramData, type Time } from "lightweight-charts";

export interface BarData {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface ChartProps {
  data: BarData[];
  width?: number;
  height?: number;
  upColor?: string;
  downColor?: string;
}

/**
 * FutuChartV2 — Lightweight candlestick chart for Futu stock data.
 * Alternative export for use in web-v2 dashboards.
 *
 * Uses lightweight-charts (TradingView) for professional-grade rendering.
 */
export function FutuChartV2({
  data,
  width,
  height = 400,
  upColor = "rgba(60, 255, 170, 0.85)",
  downColor = "rgba(242, 92, 84, 0.85)",
}: ChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

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
          color: "rgba(138, 149, 166, 0.25)", width: 1, style: 2,
          labelBackgroundColor: "rgba(10, 13, 18, 0.9)",
        },
        horzLine: {
          color: "rgba(138, 149, 166, 0.25)", width: 1, style: 2,
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
      upColor,
      downColor,
      borderUpColor: upColor,
      borderDownColor: downColor,
      wickUpColor: upColor.replace("0.85", "0.75"),
      wickDownColor: downColor.replace("0.85", "0.75"),
    });
    candleSeries.setData(data);

    // Volume histogram
    const volSeries = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volSeries.setData(
      data.map((d) => ({
        time: d.time,
        value: d.volume,
        color: d.close >= d.open
          ? "rgba(60, 255, 170, 0.35)"
          : "rgba(242, 92, 84, 0.35)",
      })),
    );

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volSeries;

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [data, width, height, upColor, downColor]);

  return (
    <div
      ref={containerRef}
      className="w-full rounded-xl overflow-hidden"
      style={{ height }}
    />
  );
}
