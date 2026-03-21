"use client";

import Image from "next/image";
import { PanelRightOpen } from "lucide-react";
import { buildAgentTraceIndex, runtimeHealth } from "@/lib/agentGridModel";
import { formatTraceTime } from "@/lib/formatTraceTime";
import { isPipelineSink, latestBeat, nextHopSummary } from "@/lib/agentCardPreview";
import type { AgentPromptSettings, NexusTrace, TopologyEdge, TopologyNode } from "@/types/nexus-payload";
import { agentAvatarStaticSrc } from "@/lib/agentAvatars";

interface AgentGridViewProps {
  nodes: TopologyNode[];
  edges?: TopologyEdge[];
  traces: NexusTrace[];
  /** Optional: show model / tools count on cards */
  agentPrompts?: AgentPromptSettings[] | null;
  selectedAgentId: string | null;
  onSelectAgent: (id: string | null) => void;
}

const statusBadge: Record<string, string> = {
  RUNNING: "border-emerald-300/70 text-emerald-100 bg-emerald-500/25",
  HOT: "border-cyan-200/80 text-cyan-100 bg-cyan-500/28",
  WARM: "border-amber-200/70 text-amber-100 bg-amber-500/22",
  STANDBY: "border-slate-500/70 text-slate-200 bg-slate-700/45",
};

const runtimeAvatarBorder: Record<string, string> = {
  RUNNING: "border-emerald-300/55",
  HOT: "border-cyan-200/55",
  WARM: "border-amber-200/55",
  STANDBY: "border-slate-400/45",
};

const runtimeNowPill: Record<string, string> = {
  RUNNING: "bg-emerald-500/12 border-emerald-300/30 text-emerald-100",
  HOT: "bg-cyan-500/12 border-cyan-200/30 text-cyan-100",
  WARM: "bg-amber-500/12 border-amber-200/30 text-amber-100",
  STANDBY: "bg-slate-700/25 border-slate-500/30 text-slate-200",
};

function promptRowFor(nodeId: string, rows: AgentPromptSettings[] | null | undefined): AgentPromptSettings | undefined {
  return rows?.find((p) => p.node_id === nodeId);
}

export function AgentGridView({ nodes, edges = [], traces, agentPrompts, selectedAgentId, onSelectAgent }: AgentGridViewProps) {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const { traceCountByNode, lastTsByNode, lastTraceByNode, latestGlobalTs } = buildAgentTraceIndex(traces);

  return (
    <div className="flex h-full min-h-0 flex-1 flex-col gap-2 overflow-hidden px-4 pb-3 pt-3">
      <div className="shrink-0">
        <div className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]">Agents · Directory</div>
      </div>

      {/* lg: 3×3 rows share remaining height so cards grow into desktop space */}
      <div
        className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto sm:grid-cols-2 sm:gap-3 lg:grid-cols-3 lg:gap-3"
      >
        {nodes.map((n) => {
          const count = traceCountByNode.get(n.id) ?? 0;
          const lastTs = lastTsByNode.get(n.id);
          const lastTrace = lastTraceByNode.get(n.id);
          const runtime = runtimeHealth(n, lastTs, latestGlobalTs);
          const badge = statusBadge[runtime];
          const selected = selectedAgentId === n.id;
          const pr = promptRowFor(n.id, agentPrompts ?? undefined);
          const toolCount = pr?.tools?.length ?? 0;
          const beat = latestBeat(lastTrace);
          const nextHop = nextHopSummary(n.id, edges, byId);
          const sink = isPipelineSink(n.id, edges);
          const avatarBorder = runtimeAvatarBorder[runtime] ?? runtimeAvatarBorder.STANDBY;
          const nowPill = runtimeNowPill[runtime] ?? runtimeNowPill.STANDBY;
          const isRunning = runtime === "RUNNING";
          const runningHighlight =
            !selected &&
            isRunning &&
            "border-[var(--nexus-glow)]/28 bg-[var(--nexus-glow)]/[0.045] shadow-[inset_0_0_0_1px_rgba(0,212,170,0.1),0_0_22px_rgba(0,212,170,0.06)]";
          return (
            <button
              key={n.id}
              type="button"
              aria-pressed={selected}
              data-active-runtime={isRunning ? "true" : undefined}
              aria-label={
                selected
                  ? "Close agent detail"
                  : isRunning
                    ? `Open ${n.label} in side panel (running)`
                    : `Open ${n.label} in side panel`
              }
              onClick={() => onSelectAgent(selected ? null : n.id)}
              className={`group relative nexus-agent-card flex min-h-[165px] flex-col overflow-hidden rounded-xl p-2.5 text-left transition-[border-color,box-shadow,background-color] duration-200 sm:p-3 lg:p-4 ${
                selected
                  ? "border-[var(--nexus-glow)]/40 bg-[var(--nexus-glow)]/[0.07] shadow-[inset_0_0_0_1px_rgba(0,212,170,0.12),0_0_18px_rgba(0,212,170,0.07)]"
                  : runningHighlight
                    ? runningHighlight
                    : "hover:border-[var(--nexus-glow)]/28 hover:shadow-[0_0_16px_rgba(0,212,170,0.06)]"
              }`}
            >
              {selected ? (
                <span
                  className="absolute left-0 top-0 h-full w-1 bg-[var(--nexus-glow)] shadow-[0_0_12px_rgba(0,212,170,0.9)]"
                  aria-hidden
                />
              ) : isRunning ? (
                <span
                  className="absolute left-0 top-0 h-full w-0.5 bg-emerald-400/70 shadow-[0_0_10px_rgba(52,211,153,0.65)]"
                  aria-hidden
                />
              ) : null}

              <div className="flex shrink-0 items-start justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <div
                    className={`relative flex h-10 w-10 items-center justify-center rounded-full border ${avatarBorder} overflow-hidden`}
                    style={
                      selected
                        ? { boxShadow: "0 0 0 1px rgba(0,212,170,0.35), 0 0 18px rgba(0,212,170,0.10)" }
                        : isRunning
                          ? { boxShadow: "0 0 0 1px rgba(52,211,153,0.28), 0 0 14px rgba(16,185,129,0.12)" }
                          : undefined
                    }
                    aria-hidden
                  >
                    <Image
                      src={agentAvatarStaticSrc(n.id)}
                      alt=""
                      fill
                      className="object-cover opacity-92"
                    />
                  </div>

                  <div className="min-w-0">
                    <div
                      className={`truncate font-mono text-sm font-semibold leading-tight transition-colors ${
                        selected
                          ? "text-[var(--nexus-glow)] nexus-glow-text"
                          : isRunning
                            ? "text-emerald-200/95"
                            : "text-[var(--nexus-text)]"
                      }`}
                    >
                      {n.label}
                    </div>
                    <div className="mt-0.5 truncate font-mono text-[10px] text-[var(--nexus-muted)]">
                      {n.actor}
                    </div>
                    <div className="mt-1 h-0.5 w-20 overflow-hidden rounded bg-transparent">
                      <div
                        className={`h-full origin-left rounded bg-gradient-to-r from-[var(--nexus-glow)]/70 to-transparent transition-transform duration-300 ${
                          selected || isRunning ? "scale-x-100 animate-pulse" : "scale-x-0"
                        }`}
                      />
                    </div>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <span
                    className={`inline-flex rounded-md p-1 transition-colors ${
                      selected
                        ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                        : "text-slate-500 opacity-80 group-hover:opacity-100 group-hover:text-slate-300"
                    }`}
                    aria-hidden
                  >
                    <PanelRightOpen className="h-4 w-4" strokeWidth={2} />
                  </span>
                  <span
                    className={`rounded-md border px-2 py-1 font-mono text-[10px] font-semibold uppercase leading-none tracking-wide ${badge}`}
                  >
                    {runtime}
                  </span>
                </div>
              </div>

              <div className="nexus-agent-card-inner-rule mt-3 flex min-h-0 flex-1 flex-col pt-3">
                <div className="flex min-h-0 items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="text-[9px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Now</div>
                    <div className="mt-1">
                      <span
                        className={`inline-flex max-w-full items-center gap-1 rounded-md border px-2 py-1 font-mono text-[11px] font-semibold leading-none ${nowPill}`}
                        title={beat ?? undefined}
                      >
                        <span className="truncate whitespace-nowrap">
                          {beat ?? (count > 0 ? "Working…" : "Waiting for signals…")}
                        </span>
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-2 grid min-h-0 flex-1 grid-cols-2 gap-2">
                  <div className="min-w-0">
                    <div className="text-[9px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">Context</div>
                    <p className="mt-1 truncate whitespace-nowrap font-mono text-[10px] leading-tight text-slate-300">
                      {n.summary ?? "—"}
                    </p>
                  </div>
                  <div className="min-w-0">
                    <div className="text-[9px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">Next</div>
                    <p className="mt-1 truncate whitespace-nowrap font-mono text-[10px] leading-tight text-slate-300">
                      {nextHop ? (
                        <>→ {nextHop}</>
                      ) : sink && edges.length > 0 ? (
                        <span className="text-[var(--nexus-muted)]">Terminal</span>
                      ) : (
                        "—"
                      )}
                    </p>
                  </div>
                </div>

                <p className="mt-auto pt-3 font-mono text-[10px] text-[var(--nexus-muted)]">
                  {count} run{count === 1 ? "" : "s"}
                  {lastTs ? ` · ${formatTraceTime(lastTs)}` : ""}
                  {toolCount > 0 ? ` · ${toolCount} tool${toolCount === 1 ? "" : "s"}` : ""}
                </p>
              </div>

            </button>
          );
        })}
      </div>
    </div>
  );
}
