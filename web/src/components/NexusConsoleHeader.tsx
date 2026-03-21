"use client";

import { Orbit, LayoutGrid } from "lucide-react";
import type { Metadata } from "@/types/nexus-payload";

export type NexusViewMode = "nexus" | "grid";

interface NexusConsoleHeaderProps {
  metadata: Metadata | null | undefined;
  viewMode: NexusViewMode;
  onViewModeChange: (mode: NexusViewMode) => void;
  viewModeTitle: string;
}

function KpiStrip({ kpis }: { kpis: Metadata["kpis"] }) {
  if (!kpis || Object.keys(kpis).length === 0) return null;

  return (
    <>
      {(kpis.pnl ?? kpis.pnl_usd) != null && (
        <div className="px-2.5 py-1 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)] font-mono text-[10px]">
          <span className="text-[var(--nexus-muted)]">PnL</span>{" "}
          <span className="text-[var(--nexus-success)]">
            {typeof kpis.pnl === "string"
              ? kpis.pnl
              : `$${Number(kpis.pnl_usd ?? kpis.pnl).toLocaleString()}`}
          </span>
        </div>
      )}
      {(kpis.win_rate ?? kpis.win_rate_pct) != null && (
        <div className="px-2.5 py-1 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)] font-mono text-[10px]">
          <span className="text-[var(--nexus-muted)]">Win Rate</span>{" "}
          <span className="text-[var(--nexus-text)]">
            {kpis.win_rate_pct != null
              ? `${Number(kpis.win_rate_pct).toFixed(1)}%`
              : `${(Number(kpis.win_rate) * 100).toFixed(1)}%`}
          </span>
        </div>
      )}
      {(kpis.sharpe ?? kpis.sharpe_ratio) != null && (
        <div className="px-2.5 py-1 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)] font-mono text-[10px]">
          <span className="text-[var(--nexus-muted)]">Sharpe</span>{" "}
          <span className="text-[var(--nexus-text)]">{String(kpis.sharpe ?? kpis.sharpe_ratio)}</span>
        </div>
      )}
      {(kpis.latency ?? kpis.latency_ms) != null && (
        <div className="px-2.5 py-1 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)] font-mono text-[10px]">
          <span className="text-[var(--nexus-muted)]">Latency</span>{" "}
          <span className="text-[var(--nexus-text)]">
            {typeof kpis.latency === "string"
              ? kpis.latency
              : `${kpis.latency_ms ?? kpis.latency}ms`}
          </span>
        </div>
      )}
      {kpis.kelly_pct != null && (
        <div className="px-2.5 py-1 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)] font-mono text-[10px]">
          <span className="text-[var(--nexus-muted)]">Kelly</span>{" "}
          <span className="text-[var(--nexus-text)]">{Number(kpis.kelly_pct)}%</span>
        </div>
      )}
    </>
  );
}

export function NexusConsoleHeader({
  metadata,
  viewMode,
  onViewModeChange,
  viewModeTitle,
}: NexusConsoleHeaderProps) {
  return (
    <header className="border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
      <div className="w-full flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">
            NEXUS TRADING CONSOLE
          </h1>
          <p className="mt-0.5 text-[10px] tracking-wide text-[var(--nexus-muted)]">
            AI Market Maker · Global telemetry, agent topology, and traceable decision flow.
          </p>
        </div>
        <div className="flex items-center gap-4 font-mono text-xs">
          {metadata?.run_id && (
            <span className="text-[var(--nexus-muted)]">
              Run: <span className="text-[var(--nexus-text)]">{metadata.run_id}</span>
            </span>
          )}
          {metadata?.ticker && (
            <span className="text-[var(--nexus-muted)]">
              Ticker: <span className="text-[var(--nexus-text)]">{metadata.ticker}</span>
            </span>
          )}
          <span className="px-2 py-1 rounded border border-[var(--nexus-glow)]/40 bg-[var(--nexus-glow)]/10 text-[var(--nexus-glow)]">
            {metadata?.status ?? "ACTIVE"}
          </span>
          <span className="px-2 py-1 rounded border border-slate-500/50 bg-slate-800/40 text-slate-200">
            OpenClaw-ready
          </span>
        </div>
      </div>

      <div className="w-full mt-2 border-t border-[var(--nexus-rule-soft)] pt-2 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 flex-1 min-w-0">
          <KpiStrip kpis={metadata?.kpis ?? {}} />
        </div>

        <div className="shrink-0" title={viewModeTitle}>
          <div className="nexus-segmented-toggle flex items-center gap-1 rounded-xl p-1">
            <button
              type="button"
              onClick={() => onViewModeChange("nexus")}
              className={`nexus-segment-btn group flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] tracking-widest uppercase transition-all ${
                viewMode === "nexus" ? "is-active" : ""
              }`}
            >
              <Orbit className="h-3.5 w-3.5 opacity-80 group-hover:opacity-100" />
              <span className="leading-none">Nexus</span>
            </button>
            <button
              type="button"
              onClick={() => onViewModeChange("grid")}
              className={`nexus-segment-btn group flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[10px] tracking-widest uppercase transition-all ${
                viewMode === "grid" ? "is-active" : ""
              }`}
            >
              <LayoutGrid className="h-3.5 w-3.5 opacity-80 group-hover:opacity-100" />
              <span className="leading-none">Agents</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
