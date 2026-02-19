"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type HistogramData,
  type Time,
  ColorType,
  CrosshairMode,
} from "lightweight-charts";

export interface KlineChartBar {
  d: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v: number;
  yc?: number | null;
}

interface KlineChartProps {
  data: KlineChartBar[];
  height?: number;
}

function toTime(dateStr: string): Time {
  const d = dateStr.length === 8
    ? `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6)}`
    : dateStr.slice(0, 10);
  return d as Time;
}

export function KlineChart({ data, height = 400 }: KlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const candleRef = useRef<ISeriesApi<any> | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const volumeRef = useRef<ISeriesApi<any> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#9ca3af",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      crosshair: { mode: CrosshairMode.Normal },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.1)",
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.1)",
        timeVisible: false,
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#ef4444",
      downColor: "#22c55e",
      borderUpColor: "#ef4444",
      borderDownColor: "#22c55e",
      wickUpColor: "#ef4444",
      wickDownColor: "#22c55e",
    });

    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });

    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleRef.current = candleSeries;
    volumeRef.current = volumeSeries;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!candleRef.current || !volumeRef.current || data.length === 0) return;

    const sorted = [...data].sort((a, b) => a.d.localeCompare(b.d));

    const candles: CandlestickData[] = sorted.map((bar) => ({
      time: toTime(bar.d),
      open: bar.o,
      high: bar.h,
      low: bar.l,
      close: bar.c,
    }));

    const volumes: HistogramData[] = sorted.map((bar) => ({
      time: toTime(bar.d),
      value: bar.v,
      color: bar.c >= bar.o ? "rgba(239,68,68,0.4)" : "rgba(34,197,94,0.4)",
    }));

    candleRef.current.setData(candles);
    volumeRef.current.setData(volumes);

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return <div ref={containerRef} className="w-full" />;
}
