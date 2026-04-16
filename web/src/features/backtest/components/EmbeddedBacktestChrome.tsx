"use client";

import { copyText } from "@/features/backtest/lib/embeddedBacktestUtils";

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
      className="shrink-0 scroll-mt-1 border-b border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 px-3 py-2"
    >
      <div className="flex h-7 w-full min-w-0 items-center gap-2">
        <span className="inline-flex h-7 shrink-0 items-center font-mono text-[9px] font-semibold uppercase tracking-widest leading-none text-[var(--nexus-glow)]">
          Backtest
        </span>
        {/* Keep stable slots so controls don't jump when switching tabs. */}
        <div className="min-w-0 grow-0 basis-[min(100%,16rem)] sm:basis-[22rem] sm:max-w-[22rem]">
          {tab === "saved" ? (
            runList.length > 0 ? (
              <select
                className="h-7 w-full min-w-0 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] px-2 font-mono text-[10px] leading-none text-[var(--nexus-text)]"
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
                <option value="">Saved runs…</option>
                {[...runList].reverse().map((id) => (
                  <option key={id} value={id} title={id}>
                    {shortRunLabel(id)}
                  </option>
                ))}
              </select>
            ) : (
              <span className="inline-flex h-7 w-full items-center rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/45 px-2 font-mono text-[9px] uppercase tracking-wider leading-none text-[var(--nexus-muted)]">
                No saved runs
              </span>
            )
          ) : (
            <span className="block h-7 w-full" aria-hidden="true" />
          )}
        </div>

        {tab === "saved" ? (
          <button
            type="button"
            disabled={historyLoading || runList.length === 0}
            onClick={() => {
              const latest = [...runList].slice(-1)[0];
              if (latest) onSelectRun(latest);
            }}
            className="h-7 w-[4.25rem] shrink-0 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)] px-2 font-mono text-[9px] uppercase tracking-wider leading-none text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)] disabled:opacity-40"
          >
            Latest
          </button>
        ) : (
          <span className="h-7 w-[4.25rem] shrink-0" aria-hidden="true" />
        )}
        <div
          className="nexus-segmented-toggle ml-auto inline-flex h-7 shrink-0 items-center gap-1 rounded-xl p-1"
          role="tablist"
          aria-label="Backtest workspace"
        >
          <button
            type="button"
            role="tab"
            aria-selected={tab === "saved"}
            onClick={() => onTabChange("saved")}
            className={`nexus-segment-btn flex h-7 items-center rounded-lg px-2.5 font-mono text-[9px] uppercase tracking-[0.18em] leading-none transition-all ${
              tab === "saved" ? "is-active" : "text-[var(--nexus-muted)]"
            }`}
          >
            Saved run
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "new"}
            onClick={() => onTabChange("new")}
            className={`nexus-segment-btn flex h-7 items-center rounded-lg px-2.5 font-mono text-[9px] uppercase tracking-[0.18em] leading-none transition-all ${
              tab === "new" ? "is-active" : "text-[var(--nexus-muted)]"
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

