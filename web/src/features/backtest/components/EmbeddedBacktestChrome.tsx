"use client";

export type EmbeddedWorkspaceTab = "saved" | "new";

export type SavedRunListItem = {
  run_id: string;
  ticker?: string | null;
  start_iso?: string | null;
  end_iso?: string | null;
  interval_sec?: number | null;
  initial_cash?: number | null;
  final_equity?: number | null;
  total_return_pct?: number | null;
  total_pnl_usd?: number | null;
  sharpe?: number | null;
  total_trades?: number | null;
  eval_bars?: number | null;
  equity_points?: number | null;
  has_charts?: boolean;
  sort_ts?: number;
};

type Props = {
  tab: EmbeddedWorkspaceTab;
  onTabChange: (t: EmbeddedWorkspaceTab) => void;
  jobRunning?: boolean;
  jobStep?: number;
  jobTotal?: number;
  jobEquity?: number | null;
  jobClosed?: number;
  jobOpen?: number;
  jobWarmup?: boolean;
  onResumeRunning?: () => void;
  reportReady?: boolean;
  onOpenReport?: () => void;
  savedDetailOpen?: boolean;
};

export function EmbeddedBacktestChrome({
  tab,
  onTabChange,
  jobRunning = false,
  jobStep = 0,
  jobTotal = 0,
  jobEquity = null,
  jobClosed = 0,
  jobOpen = 0,
  jobWarmup = false,
  onResumeRunning,
  reportReady = false,
  onOpenReport,
  savedDetailOpen = false,
}: Props) {
  const pct =
    jobWarmup || jobTotal <= 0
      ? 0
      : Math.min(100, Math.round((jobStep / jobTotal) * 100));

  const tabBtn =
    "relative -mb-px border-b-2 px-1 pb-2 font-mono text-[10px] uppercase tracking-[0.16em] transition-colors";

  return (
    <div
      id="backtest-embedded-summary"
      className="shrink-0 scroll-mt-1 border-b border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 px-3 pt-2"
    >
      <div className="flex h-7 w-full min-w-0 items-center gap-2">
        <span className="inline-flex h-7 shrink-0 items-center font-mono text-[9px] font-semibold uppercase tracking-widest leading-none text-[var(--nexus-glow)]">
          Backtest
        </span>
        <div className="min-w-0 flex-1 font-mono text-[9px] text-[var(--nexus-muted)]">
          {tab === "saved"
            ? savedDetailOpen
              ? "Statistical report"
              : "Saved runs · newest first"
            : jobRunning
              ? jobWarmup
                ? "Preparing…"
                : "Running…"
              : reportReady
                ? "Finished"
                : "New replay"}
        </div>
      </div>

      <div
        className="mt-1 flex items-end gap-4"
        role="tablist"
        aria-label="Backtest workspace"
      >
        <button
          type="button"
          role="tab"
          aria-selected={tab === "saved"}
          onClick={() => onTabChange("saved")}
          className={`${tabBtn} ${
            tab === "saved"
              ? "border-[var(--nexus-glow)] text-[var(--nexus-glow)]"
              : "border-transparent text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
          }`}
        >
          Saved run
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "new"}
          onClick={() => onTabChange("new")}
          className={`${tabBtn} inline-flex items-center gap-1.5 ${
            tab === "new"
              ? "border-[var(--nexus-glow)] text-[var(--nexus-glow)]"
              : "border-transparent text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
          }`}
        >
          New backtest
          {jobRunning ? (
            <span
              className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--nexus-glow)]"
              aria-hidden
            />
          ) : null}
        </button>
      </div>

      {jobRunning ? (
        <div className="mt-2 mb-2 rounded-lg bg-[var(--nexus-glow)]/8 px-2.5 py-2 ring-1 ring-[color:var(--nexus-glow)]/25">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-glow)]">
              {jobWarmup ? "Preparing…" : `${jobStep}/${jobTotal || "…"} · ${pct}%`}
            </p>
            {tab !== "new" && onResumeRunning ? (
              <button
                type="button"
                onClick={onResumeRunning}
                className="rounded-md bg-[var(--nexus-glow)]/15 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[var(--nexus-glow)]/25"
              >
                Progress
              </button>
            ) : null}
          </div>
          <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--nexus-surface)]">
            <div
              className="h-full bg-[var(--nexus-glow)] transition-[width] duration-300"
              style={{ width: `${pct}%` }}
            />
          </div>
          {!jobWarmup ? (
            <p
              className="mt-1 font-mono text-[9px] text-[var(--nexus-muted)]"
              title="Equity is mark-to-market. Closed = finished round-trips; open positions can move equity with 0 closed."
            >
              Equity{" "}
              {typeof jobEquity === "number"
                ? `$${jobEquity.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                : "…"}
              {jobOpen > 0 ? ` · ${jobOpen} open` : ""}
              {` · ${jobClosed} closed`}
            </p>
          ) : null}
        </div>
      ) : reportReady && onOpenReport ? (
        <div className="mt-2 mb-2 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-[var(--nexus-glow)]/8 px-2.5 py-2 ring-1 ring-[color:var(--nexus-glow)]/25">
          <p className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-glow)]">
            Finished
          </p>
          <button
            type="button"
            onClick={onOpenReport}
            className="rounded-md bg-[var(--nexus-glow)] px-2.5 py-1 font-mono text-[9px] font-semibold uppercase tracking-wider text-[var(--nexus-bg)] hover:brightness-110"
          >
            View report
          </button>
        </div>
      ) : (
        <div className="h-2" aria-hidden />
      )}
    </div>
  );
}
