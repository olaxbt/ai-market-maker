"use client";

import { copyText } from "./embeddedBacktestUtils";

export type EmbeddedWorkspaceTab = "saved" | "new";

type Props = {
  tab: EmbeddedWorkspaceTab;
  onTabChange: (t: EmbeddedWorkspaceTab) => void;
  runList: string[];
  selectedHistoryId: string;
  historyLoading: boolean;
  activeRunId: string;
  shortRunLabel: (id: string) => string;
  onSelectRun: (runId: string) => void;
  onClearRun: () => void;
};

export function EmbeddedBacktestChrome({
  tab,
  onTabChange,
  runList,
  selectedHistoryId,
  historyLoading,
  activeRunId,
  shortRunLabel,
  onSelectRun,
  onClearRun,
}: Props) {
  return (
    <div
      id="backtest-embedded-summary"
      className="shrink-0 scroll-mt-1 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/50 px-2 py-2"
    >
      <div className="flex w-full min-w-0 flex-wrap items-center gap-x-2 gap-y-1.5">
        <span className="shrink-0 font-mono text-[9px] font-semibold uppercase tracking-widest text-[var(--nexus-glow)]">
          Backtest
        </span>
        {tab === "saved" ? (
          <div className="min-w-0 flex-1 basis-[min(100%,14rem)] sm:max-w-[min(100%,24rem)]">
            {runList.length > 0 ? (
              <select
                className="h-7 w-full min-w-0 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] px-2 font-mono text-[10px] text-[var(--nexus-text)]"
                value={selectedHistoryId}
                disabled={historyLoading}
                title={selectedHistoryId ? `Full id: ${selectedHistoryId}` : "Saved runs"}
                aria-label="Browse saved backtest runs"
                onChange={(e) => {
                  const id = e.target.value.trim();
                  if (id) onSelectRun(id);
                  else onClearRun();
                }}
              >
                <option value="">Runs…</option>
                {[...runList].reverse().map((id) => (
                  <option key={id} value={id} title={id}>
                    {shortRunLabel(id)}
                  </option>
                ))}
              </select>
            ) : (
              <span className="font-mono text-[9px] text-[var(--nexus-muted)]">No saved runs</span>
            )}
          </div>
        ) : (
          <span className="min-w-0 flex-1" aria-hidden="true" />
        )}
        <div
          className="ml-auto inline-flex shrink-0 rounded border border-[color:var(--nexus-card-stroke)] p-px"
          role="tablist"
          aria-label="Backtest workspace"
        >
          <button
            type="button"
            role="tab"
            aria-selected={tab === "saved"}
            onClick={() => onTabChange("saved")}
            className={`rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wide ${
              tab === "saved"
                ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
            }`}
          >
            Saved run
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "new"}
            onClick={() => onTabChange("new")}
            className={`rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wide ${
              tab === "new" ? "bg-amber-500/15 text-amber-200/95" : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
            }`}
          >
            New backtest
          </button>
        </div>
      </div>
      {tab === "saved" && (historyLoading || activeRunId) ? (
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 border-t border-[var(--nexus-rule-soft)] pt-1.5 font-mono text-[10px]">
          <span className="shrink-0 text-[var(--nexus-muted)]">Id</span>
          {historyLoading ? (
            <span className="animate-pulse text-[var(--nexus-glow)]">loading…</span>
          ) : (
            <div className="inline-flex min-w-0 max-w-full items-center gap-1.5 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/50 py-0.5 pl-1.5 pr-0.5">
              <span className="min-w-0 truncate text-[var(--nexus-glow)]" title={activeRunId}>
                {activeRunId}
              </span>
              <button
                type="button"
                onClick={() => void copyText(activeRunId)}
                className="shrink-0 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/80 px-1.5 py-0.5 text-[9px] uppercase text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/40 hover:text-[var(--nexus-text)]"
              >
                Copy
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
