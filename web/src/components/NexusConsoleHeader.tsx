"use client";

import { Suspense, useEffect } from "react";
import { NexusHeaderNav } from "@/components/NexusHeaderNav";
import { ThemeToggleButton } from "@/components/ThemeProvider";
import type { Metadata } from "@/types/nexus-payload";

export type NexusViewMode = "nexus" | "grid" | "backtest" | "supervisor" | "monitor" | "research" | "futu";

export const NEXUS_LAST_RUN_ID_KEY = "nexus_last_run_id_v1";

interface NexusConsoleHeaderProps {
  metadata: Metadata | null | undefined;
  viewMode: NexusViewMode;
  wsConnected?: boolean;
  loading?: boolean;
  lastUpdateIso?: string | null;
  /** From HTTP `/api/traces` or client mock mode — shown as a small badge */
  traceDataSource?: string | null;
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
          <span className="text-[var(--nexus-text)]">
            {String(kpis.sharpe ?? kpis.sharpe_ratio)}
          </span>
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
  wsConnected,
  loading,
  lastUpdateIso,
  traceDataSource,
}: NexusConsoleHeaderProps) {
  useEffect(() => {
    const runId = metadata?.run_id;
    if (!runId) return;
    try {
      sessionStorage.setItem(NEXUS_LAST_RUN_ID_KEY, String(runId));
    } catch {
      // ignore
    }
  }, [metadata?.run_id]);

  const title =
    viewMode === "futu"
      ? "FUTU OPEND"
      : viewMode === "backtest"
        ? "BACKTEST LAB"
        : viewMode === "supervisor"
          ? "SUPERVISOR CONSOLE"
          : viewMode === "research"
            ? "RESEARCH WORKSPACE"
            : viewMode === "grid"
              ? "AGENTS CONSOLE"
              : viewMode === "monitor"
                ? "LIVE MONITOR"
                : "NEXUS TRADING CONSOLE";
  return (
    <header className="relative border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
      <div className="w-full">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">
              {title}
            </h1>
            <p className="mt-0.5 min-h-[1.5rem] text-[10px] leading-snug tracking-wide text-[var(--nexus-muted)]">
              {viewMode === "futu"
                ? "HK & US stock market data via Futu OpenD gateway."
                : viewMode === "backtest"
                  ? "Replay saved runs, run new backtests, and inspect per-bar agent traces."
                  : viewMode === "supervisor"
                    ? "Ask questions and get an executive snapshot for a saved run."
                    : viewMode === "research"
                      ? "Compact backtest + supervisor side-by-side (shared run context)."
                      : viewMode === "grid"
                        ? "Browse desks and agents. Inspect traces and edit prompts (where applicable)."
                        : viewMode === "monitor"
                          ? "Balances, positions, and last decisions — designed for always-on ops."
                          : "AI Market Maker · Global telemetry, agent topology, and traceable decision flow."}
            </p>
          </div>
          <div className="shrink-0 pt-0.5">
            <ThemeToggleButton />
          </div>
        </div>

        <div className="w-full mt-2 border-t border-[var(--nexus-rule-soft)] pt-2 flex flex-wrap items-center justify-start gap-3">
          <div className="min-w-0 flex-1">
            <Suspense fallback={<div className="h-10 w-full max-w-md rounded-lg bg-[var(--nexus-surface)]" />}>
              <NexusHeaderNav />
            </Suspense>
          </div>
          {traceDataSource ? (
            <span
              className={`rounded-lg border px-2 py-1 text-[10px] font-mono ${
                traceDataSource === "live"
                  ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.06)] text-[var(--nexus-text)]"
                  : traceDataSource === "mock-offline"
                    ? "border-[rgba(59,130,246,0.28)] bg-[rgba(59,130,246,0.08)] text-[rgba(147,197,253,0.95)]"
                    : "border-[rgba(245,158,11,0.28)] bg-[rgba(245,158,11,0.08)] text-[rgba(245,158,11,0.95)]"
              }`}
              title="Initial graph payload source: live = from your Flow run log; mock = bundled demo only (NEXT_PUBLIC_USE_MOCK=1); mock-fallback = Flow unreachable; not related to LLM on/off."
            >
              payload: {traceDataSource}
            </span>
          ) : null}
          <span
            className={`rounded-lg border px-2 py-1 text-[10px] font-mono ${
              wsConnected
                ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[var(--nexus-text)]"
                : "border-[var(--nexus-border)] bg-[var(--nexus-surface)] text-[var(--nexus-muted)]"
            }`}
            title="WebSocket stream connection"
          >
            {wsConnected ? "stream: connected" : "stream: offline"}
          </span>
          <span
            className="rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface)] px-2 py-1 text-[10px] font-mono text-[var(--nexus-muted)]"
            title="Last payload update time"
          >
            {loading ? "updating…" : lastUpdateIso ? `last: ${new Date(lastUpdateIso).toLocaleTimeString()}` : "last: —"}
          </span>
          {metadata?.run_id ? (
            <span className="rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface)] px-2 py-1 text-[10px] font-mono text-[var(--nexus-muted)]">
              run: <span className="text-[var(--nexus-text)]">{metadata.run_id}</span>
            </span>
          ) : null}
          <KpiStrip kpis={metadata?.kpis ?? {}} />
        </div>
      </div>
    </header>
  );
}
