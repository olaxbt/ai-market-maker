"use client";

import { Suspense, useEffect } from "react";
import { NexusHeaderNav } from "@/components/NexusHeaderNav";
import type { Metadata } from "@/types/nexus-payload";

export type NexusViewMode =
  | "nexus"
  | "grid"
  | "backtest"
  | "supervisor"
  | "monitor"
  | "portfolio"
  | "research"
  | "futu";

export const NEXUS_LAST_RUN_ID_KEY = "nexus_last_run_id_v1";

interface NexusConsoleHeaderProps {
  metadata: Metadata | null | undefined;
  viewMode: NexusViewMode;
  wsConnected?: boolean;
  loading?: boolean;
  lastUpdateIso?: string | null;
  traceDataSource?: string | null;
  sessionActive?: boolean;
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
  sessionActive = false,
}: NexusConsoleHeaderProps) {
  useEffect(() => {
    const runId = metadata?.run_id;
    if (!runId || runId === "latest") return;
    try {
      sessionStorage.setItem(NEXUS_LAST_RUN_ID_KEY, String(runId));
    } catch {
      // ignore
    }
  }, [metadata?.run_id]);

  const title =
    viewMode === "futu"
      ? "STOCK QUOTES"
      : viewMode === "backtest"
        ? "BACKTEST LAB"
        : viewMode === "supervisor"
          ? "SUPERVISOR"
          : viewMode === "research"
            ? "RESEARCH"
            : viewMode === "grid"
              ? "AGENTS"
          : viewMode === "monitor" || viewMode === "portfolio"
            ? "PORTFOLIO"
            : "LIVE DESK";

  let subtitle = "AI Market Maker console.";
  if (viewMode === "futu") {
    subtitle = "Optional OpenD quotes (not required for agentic backtests).";
  } else if (viewMode === "backtest") {
    subtitle = "Replay saved runs and inspect per-bar agent traces.";
  } else if (viewMode === "supervisor") {
    subtitle = "Ask questions about a completed backtest run.";
  } else if (viewMode === "research") {
    subtitle =
      "Backtests + Supervisor in one console — fine-tune agents while Live keeps the book.";
  } else if (viewMode === "grid") {
    subtitle = "Agent roster and prompts.";
  } else if (viewMode === "monitor" || viewMode === "portfolio") {
    subtitle = "Live book equity, cash, positions, and risk.";
  } else {
    subtitle = "Paper session and agent thoughts.";
  }

  const hideRunInMeta = viewMode === "nexus" || viewMode === "grid";

  const sessionLabel = sessionActive
    ? wsConnected
      ? "Session · live"
      : "Session · has run data"
    : "Session · idle";

  return (
    <header className="relative border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
      <div className="w-full">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">
              {title}
            </h1>
            <p className="mt-0.5 min-h-[1.5rem] max-w-3xl text-[10px] leading-snug tracking-wide text-[var(--nexus-muted)]">
              {subtitle}
            </p>
          </div>
          <span
            className={`inline-flex shrink-0 items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider ${
              sessionActive ? "text-[var(--nexus-glow)]" : "text-[var(--nexus-muted)]"
            }`}
            title={
              viewMode === "monitor" || viewMode === "portfolio"
                ? "Portfolio is the live/paper book only — open Research for backtests."
                : "Live and Research are separate lanes; both can be active while you tune agents."
            }
            role="status"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                sessionActive
                  ? wsConnected
                    ? "bg-[var(--nexus-glow)] shadow-[0_0_6px_rgba(0,212,170,0.65)]"
                    : "bg-[var(--nexus-glow)]/70"
                  : "bg-[var(--nexus-muted)]/50"
              }`}
              aria-hidden
            />
            {sessionLabel}
          </span>
        </div>

        <div className="mt-2 flex w-full flex-col gap-2 border-t border-[var(--nexus-rule-soft)] pt-2 lg:flex-row lg:flex-wrap lg:items-center lg:justify-start lg:gap-3">
          <div className="min-w-0 w-full lg:flex-1">
            <Suspense fallback={<div className="h-10 w-full max-w-md rounded-lg bg-[var(--nexus-surface)]" />}>
              <NexusHeaderNav />
            </Suspense>
          </div>
          <div className="flex w-full min-w-0 flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] text-[var(--nexus-muted)] lg:w-auto lg:shrink-0">
            {traceDataSource && traceDataSource !== "idle" ? (
              <span
                className={traceDataSource === "live" ? "text-[var(--nexus-text)]" : "text-[rgba(245,158,11,0.95)]"}
                title="Graph payload source"
              >
                data: {traceDataSource}
              </span>
            ) : null}
            <span title="Live WebSocket from the Flow API" className={wsConnected ? "text-[var(--nexus-text)]" : undefined}>
              {wsConnected ? "stream on" : "stream off"}
            </span>
            <span title="Last agent-event update">
              {loading ? "updating…" : lastUpdateIso ? `last: ${new Date(lastUpdateIso).toLocaleTimeString()}` : "last: —"}
            </span>
            {!hideRunInMeta && metadata?.run_id && metadata.run_id !== "latest" ? (
              <span>
                run: <span className="text-[var(--nexus-text)]">{metadata.run_id}</span>
              </span>
            ) : null}
            {sessionActive ? <KpiStrip kpis={metadata?.kpis ?? {}} /> : null}
          </div>
        </div>
      </div>
    </header>
  );
}
