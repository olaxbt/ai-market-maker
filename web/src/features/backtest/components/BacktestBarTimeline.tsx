"use client";

import { ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AgentTraceCard } from "@/components/AgentTraceCard";
import { formatTraceTime } from "@/lib/formatTraceTime";
import {
  groupBacktestMessageLog,
  shortenOutline,
  stripLegacyBarPrefix,
  type BarTimelineGroup,
} from "@/lib/groupBacktestMessageLog";
import { tracesForBarGroup } from "@/lib/tracesForBar";
import type { MessageLogEntry, NexusTrace } from "@/types/nexus-payload";

type Props = {
  entries: MessageLogEntry[];
  traces?: NexusTrace[];
  streaming?: boolean;
  className?: string;
  emptyHint?: string | null;
  compact?: boolean;
};

function moduleChipClass(): string {
  return "rounded-md border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/45 pl-2.5 border-l-[3px] border-l-[var(--nexus-glow)]/35";
}

function displayMessage(e: MessageLogEntry): string {
  if (typeof e.bar_step === "number") return e.message;
  return stripLegacyBarPrefix(e.message).rest;
}

function statusPill(status: BarTimelineGroup["status"]) {
  if (status === "running") {
    return (
      <span className="rounded border border-[var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/10 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-glow)]">
        Running
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="rounded border border-red-500/40 bg-red-950/40 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-red-200/95">
        Error
      </span>
    );
  }
  return (
    <span className="rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/50 px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
      Done
    </span>
  );
}

function outlineForGroup(g: BarTimelineGroup): { actor: string; line: string }[] {
  const seen = new Set<string>();
  const out: { actor: string; line: string }[] = [];
  for (const e of g.entries) {
    if (seen.has(e.actor_id)) continue;
    seen.add(e.actor_id);
    out.push({ actor: e.actor_id, line: shortenOutline(displayMessage(e), 64) });
    if (out.length >= 24) break;
  }
  return out;
}

function compactOutlineSummary(lines: { actor: string; line: string }[]): string {
  if (lines.length === 0) return "";
  const max = 8;
  const head = lines.slice(0, max).map((l) => l.actor);
  const more = lines.length > max ? ` · +${lines.length - max}` : "";
  return `${head.join(" · ")}${more}`;
}

export function BacktestBarTimeline({
  entries,
  traces = [],
  streaming,
  className,
  emptyHint,
  compact = false,
}: Props) {
  const groups = useMemo(() => groupBacktestMessageLog(entries, streaming ?? false), [entries, streaming]);
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const containerRef = useRef<HTMLDivElement>(null);
  const stickBottomRef = useRef(true);

  const lastKey = groups.length ? groups[groups.length - 1].key : null;

  useEffect(() => {
    if (lastKey && streaming) {
      setOpen((o) => ({ ...o, [lastKey]: true }));
    }
  }, [lastKey, streaming]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const NEAR = 120;
    const onScroll = () => {
      const d = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickBottomRef.current = d <= NEAR;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || !stickBottomRef.current) return;
    el.scrollTop = el.scrollHeight;
  }, [groups.length, entries.length]);

  const toggle = (key: string) => setOpen((o) => ({ ...o, [key]: !o[key] }));

  const detailGrid = compact
    ? "grid min-h-0 grid-cols-1 gap-2 min-[720px]:grid-cols-2 min-[720px]:gap-2.5"
    : "grid min-h-0 grid-cols-1 gap-4 lg:grid-cols-2 lg:gap-5";

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="Backtest timeline by bar"
      className={`nexus-scroll overflow-y-auto overflow-x-hidden ${className ?? ""}`}
    >
      {streaming && entries.length === 0 ? (
        <p className={compact ? "text-[10px] text-[var(--nexus-muted)]" : "text-[13px] leading-relaxed text-[var(--nexus-muted)]"}>
          Waiting for events…
        </p>
      ) : null}
      {!streaming && entries.length === 0 ? (
        <p
          className={
            compact
              ? "text-[10px] leading-snug text-[var(--nexus-muted)]"
              : "max-w-prose text-[13px] leading-relaxed text-[var(--nexus-muted)]"
          }
        >
          {emptyHint?.trim() ? emptyHint : "No events yet. Run a backtest or load a completed run."}
        </p>
      ) : null}

      <div className={compact ? "space-y-0.5" : "space-y-2"}>
        {groups.map((g) => {
          const isOpen = open[g.key] ?? false;
          const lines = outlineForGroup(g);
          const barTraces = tracesForBarGroup(g, traces);
          const summaryLine = compactOutlineSummary(lines);
          const hasCoT = barTraces.length > 0;
          const logColSpan = !hasCoT ? "min-[720px]:col-span-2" : "";

          return (
            <div
              key={g.key}
              className={`border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/75 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.03)] ${
                compact ? "rounded-md" : "rounded-xl"
              }`}
            >
              <button
                type="button"
                onClick={() => toggle(g.key)}
                className={`sticky top-0 z-10 flex w-full items-start gap-1.5 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/95 text-left shadow-[0_6px_12px_-8px_rgba(0,0,0,0.45)] backdrop-blur-sm transition hover:bg-[var(--nexus-surface)]/55 ${
                  compact ? "px-2 py-1.5" : "gap-3 px-3 py-3 sm:px-4 sm:py-3.5"
                }`}
              >
                <span className={`shrink-0 text-[var(--nexus-muted)] ${compact ? "mt-px" : "mt-1"}`}>
                  {isOpen ? <ChevronDown size={compact ? 14 : 18} strokeWidth={2} /> : <ChevronRight size={compact ? 14 : 18} strokeWidth={2} />}
                </span>
                <div className="min-w-0 flex-1">
                  {compact ? (
                    <>
                      <div className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5">
                        <span className="font-mono text-[11px] font-semibold tracking-tight text-[var(--nexus-glow)]">{g.title}</span>
                        {g.barTimeUtc ? (
                          <>
                            <span className="text-[10px] text-[var(--nexus-muted)]">·</span>
                            <span className="font-mono text-[10px] text-[var(--nexus-muted)]">{g.barTimeUtc}</span>
                          </>
                        ) : null}
                        {statusPill(g.status)}
                      </div>
                      {!isOpen && summaryLine ? (
                        <p className="mt-0.5 truncate font-mono text-[9px] leading-snug text-[var(--nexus-muted)]" title={summaryLine}>
                          {summaryLine}
                        </p>
                      ) : null}
                    </>
                  ) : (
                    <>
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                        <span className="font-mono text-[13px] font-semibold tracking-tight text-[var(--nexus-glow)]">{g.title}</span>
                        {g.barTimeUtc ? <span className="font-mono text-[12px] text-[var(--nexus-muted)]">{g.barTimeUtc}</span> : null}
                        {statusPill(g.status)}
                      </div>
                      {!isOpen ? (
                        <div className="mt-2.5 flex max-h-[3.25rem] flex-wrap gap-2 overflow-hidden">
                          {lines.slice(0, 5).map(({ actor, line }) => (
                            <span key={actor} className={`inline-block max-w-full font-mono text-[11px] leading-snug text-[var(--nexus-text)] ${moduleChipClass()}`}>
                              <span className="font-semibold text-[var(--nexus-glow)]">{actor}</span>
                              <span className="text-[var(--nexus-muted)]"> · </span>
                              <span>{line}</span>
                            </span>
                          ))}
                          {lines.length > 5 ? <span className="self-center font-mono text-[10px] text-[var(--nexus-muted)]">+{lines.length - 5}</span> : null}
                        </div>
                      ) : null}
                    </>
                  )}
                </div>
              </button>

              {isOpen ? (
                <div className={`border-t border-[var(--nexus-rule-soft)] bg-[var(--nexus-bg)]/35 ${compact ? "px-2 py-1.5" : "px-3 py-4 sm:px-5 sm:py-5"}`}>
                  <div className={detailGrid}>
                    {hasCoT ? (
                      <div className="flex min-h-0 min-w-0 flex-col">
                        <h4
                          className={`font-mono font-semibold uppercase tracking-[0.15em] text-[var(--nexus-text)] ${
                            compact ? "mb-1.5 text-[9px]" : "mb-3 text-[11px] tracking-[0.18em]"
                          }`}
                        >
                          Chain of thought
                        </h4>
                        <div
                          role="region"
                          aria-label="Chain of thought for this bar"
                          className={`nexus-scroll min-h-0 overflow-y-auto overflow-x-hidden overscroll-y-contain ${
                            compact ? "max-h-[min(50vh,28rem)] space-y-2 pr-0.5" : "max-h-[min(55vh,32rem)] space-y-3 pr-1"
                          }`}
                        >
                          {barTraces.map((tr, i) => (
                            <AgentTraceCard key={tr.trace_id} trace={tr} index={i} reduceMotion surface="timeline" className="!mb-0 shadow-md" />
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div
                      className={`flex min-h-0 min-w-0 flex-col ${logColSpan} ${
                        hasCoT ? "border-t border-[var(--nexus-rule-soft)] pt-3 min-[720px]:border-t-0 min-[720px]:pt-0" : ""
                      }`}
                    >
                      <h4
                        className={`font-mono font-semibold uppercase tracking-[0.15em] text-[var(--nexus-text)] ${
                          compact ? "mb-1.5 text-[9px]" : "mb-3 text-[11px] tracking-[0.18em]"
                        }`}
                      >
                        Event log
                      </h4>
                      {!compact ? (
                        <p className="mb-3 text-[12px] leading-relaxed text-[var(--nexus-muted)]">
                          Events oldest → newest. Wide payloads scroll inside each row.
                        </p>
                      ) : null}
                      <div
                        role="region"
                        aria-label="Event log for this bar"
                        className={`nexus-scroll min-h-0 overflow-y-auto overflow-x-auto overscroll-y-contain rounded-md border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/50 ${
                          compact ? "max-h-[min(50vh,28rem)]" : "max-h-[min(55vh,32rem)] rounded-xl shadow-[inset_0_1px_0_0_rgba(255,255,255,0.04)]"
                        }`}
                      >
                        <div className="min-w-0 divide-y divide-[var(--nexus-rule-soft)]">
                          {g.entries.map((row, idx) => (
                            <div
                              key={row.seq}
                              className={`select-text ${compact ? "px-2 py-2" : "px-3 py-3.5 sm:px-4 sm:py-4"} ${
                                idx % 2 === 0 ? "bg-[var(--nexus-surface)]/15" : "bg-[var(--nexus-bg)]/25"
                              }`}
                            >
                              <div className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5">
                                <span
                                  className={`inline-flex items-center rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60 font-mono tabular-nums text-[var(--nexus-text)] ${
                                    compact ? "px-1 py-px text-[9px]" : "px-2 py-0.5 text-[11px]"
                                  }`}
                                >
                                  {formatTraceTime(row.ts)}
                                </span>
                                <span
                                  className={`inline-flex max-w-full items-center rounded border border-[var(--nexus-glow)]/35 bg-[var(--nexus-glow)]/10 font-mono font-medium text-[var(--nexus-glow)] ${
                                    compact ? "px-1 py-px text-[9px]" : "px-2 py-0.5 text-[11px]"
                                  }`}
                                >
                                  {row.actor_id}
                                </span>
                                <span
                                  className={`inline-flex items-center rounded border border-[color:var(--nexus-card-stroke)] font-mono uppercase tracking-wide text-[var(--nexus-muted)] ${
                                    compact ? "px-1 py-px text-[8px]" : "px-2 py-0.5 text-[10px]"
                                  }`}
                                >
                                  {row.kind}
                                </span>
                              </div>
                              <div
                                className={`mt-1.5 overflow-x-auto rounded border border-[color:var(--nexus-card-stroke)] bg-black/25 ${
                                  compact ? "px-2 py-1.5" : "mt-3 px-3 py-3 sm:px-4"
                                }`}
                              >
                                <p
                                  className={`min-w-0 whitespace-pre-wrap break-words font-mono text-[var(--nexus-text)] ${
                                    compact ? "text-[11px] leading-snug" : "text-[13px] leading-[1.65]"
                                  }`}
                                >
                                  {displayMessage(row)}
                                </p>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

