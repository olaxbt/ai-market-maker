"use client";

import { useMemo, useState } from "react";
import { AgentDetailPanel } from "@/components/AgentDetailPanel";
import { AgentGridView } from "@/components/AgentGridView";
import type { AgentPromptSettings, NexusTrace, TopologyEdge, TopologyNode } from "@/types/nexus-payload";

interface AgentsConsoleViewProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  traces: NexusTrace[];
  agentPrompts: AgentPromptSettings[] | null | undefined;
  selectedAgentId: string | null;
  onSelectAgent: (id: string | null) => void;
  selectedAgentTraces: NexusTrace[];
  selectedAgentNode: TopologyNode | null;
  selectedAgentPrompt: AgentPromptSettings | null;
  streaming: boolean;
}

type AgentsViewFilter = "desk" | "llm" | "full";

const DESK_NODE_IDS = new Set(["n1", "n11", "n12", "n13", "n14", "n16"]);
const DESK_ORDER = ["n1", "n11", "n12", "n13", "n14", "n16"];

function promptModeFor(
  nodeId: string,
  rows: AgentPromptSettings[] | null | undefined,
): { applies: boolean; mode: string } {
  const r = rows?.find((x) => x.node_id === nodeId);
  const applies =
    !!r && typeof r === "object" && "applies_to_runtime" in r
      ? Boolean((r as unknown as { applies_to_runtime?: boolean }).applies_to_runtime)
      : false;
  const mode =
    !!r && typeof r === "object" && "mode" in r
      ? String((r as unknown as { mode?: string }).mode ?? "")
      : "";
  return { applies, mode };
}

export function AgentsConsoleView({
  nodes,
  edges,
  traces,
  agentPrompts,
  selectedAgentId,
  onSelectAgent,
  selectedAgentTraces,
  selectedAgentNode,
  selectedAgentPrompt,
  streaming,
}: AgentsConsoleViewProps) {
  const [filter, setFilter] = useState<AgentsViewFilter>("desk");

  const filteredNodes = useMemo(() => {
    if (filter === "full") return nodes;
    if (filter === "desk") {
      const byId = new Map(nodes.map((n) => [n.id, n]));
      return DESK_ORDER.map((id) => byId.get(id)).filter(Boolean) as TopologyNode[];
    }
    // llm
    return nodes.filter((n) => promptModeFor(n.id, agentPrompts).applies);
  }, [nodes, filter, agentPrompts]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((n) => n.id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (filter === "full") return edges;
    return edges.filter((e) => filteredNodeIds.has(e.from) && filteredNodeIds.has(e.to));
  }, [edges, filter, filteredNodeIds]);

  const filteredTraces = useMemo(() => {
    if (filter === "full") return traces;
    return traces.filter((t) => filteredNodeIds.has(t.node_id));
  }, [traces, filter, filteredNodeIds]);

  const selectedAgentTracesFiltered = useMemo(() => {
    if (!selectedAgentId) return [];
    return filteredTraces.filter((t) => t.node_id === selectedAgentId);
  }, [filteredTraces, selectedAgentId]);

  const selectedAgentNodeFiltered = useMemo(() => {
    if (!selectedAgentId) return null;
    return filteredNodes.find((n) => n.id === selectedAgentId) ?? null;
  }, [filteredNodes, selectedAgentId]);

  const selectedAgentPromptFiltered = useMemo(() => {
    if (!selectedAgentId) return null;
    return (agentPrompts ?? []).find((p) => p.node_id === selectedAgentId) ?? null;
  }, [agentPrompts, selectedAgentId]);

  const whatsHappening = useMemo(() => {
    if (filter !== "desk") return null;
    const latestByNode = new Map<string, NexusTrace>();
    for (const t of filteredTraces) {
      const prev = latestByNode.get(t.node_id);
      if (!prev || t.timestamp > prev.timestamp) latestByNode.set(t.node_id, t);
    }
    const lines = DESK_ORDER.map((id) => {
      const n = filteredNodes.find((x) => x.id === id);
      const tr = latestByNode.get(id);
      const now =
        tr?.content?.thought_process?.[0]?.detail ??
        (tr?.content?.context?.signal != null ? `signal=${String(tr.content.context.signal)}` : null) ??
        n?.summary ??
        "—";
      return { id, label: n?.label ?? id, now: String(now).slice(0, 140) };
    });
    return lines;
  }, [filter, filteredTraces, filteredNodes]);

  return (
    <main className="flex flex-1 min-h-0 w-full flex-col overflow-hidden lg:flex-row lg:items-stretch">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <div className="shrink-0 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/60 px-4 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]">
              View
            </div>
            <div className="flex items-center gap-1.5">
              {([
                ["desk", "Desk"],
                ["llm", "LLM-only"],
                ["full", "Full graph"],
              ] as const).map(([id, label]) => {
                const active = filter === id;
                return (
                  <button
                    key={id}
                    type="button"
                    onClick={() => {
                      setFilter(id);
                      // If current selection is filtered out, close detail.
                      if (selectedAgentId && id !== "full") {
                        const keep =
                          id === "desk"
                            ? DESK_NODE_IDS.has(selectedAgentId)
                            : promptModeFor(selectedAgentId, agentPrompts).applies;
                        if (!keep) onSelectAgent(null);
                      }
                    }}
                    className={`rounded-md border px-2.5 py-1 font-mono text-[10px] uppercase tracking-widest transition-colors ${
                      active
                        ? "border-[var(--nexus-glow)]/50 bg-[var(--nexus-glow)]/10 text-[var(--nexus-glow)]"
                        : "border-[var(--nexus-border)] bg-[var(--nexus-surface)]/60 text-slate-200 hover:border-[var(--nexus-glow)]/35"
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        {whatsHappening ? (
          <div className="shrink-0 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/40 px-4 py-2">
            <div className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]">
              What’s happening
            </div>
            <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {whatsHappening.map((row) => (
                <div
                  key={row.id}
                  className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/25 px-3 py-2"
                >
                  <div className="font-mono text-[10px] font-semibold uppercase tracking-widest text-slate-200">
                    {row.label}
                  </div>
                  <div className="mt-1 font-mono text-[10px] leading-relaxed text-[var(--nexus-muted)]">
                    {row.now}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
        <AgentGridView
          nodes={filteredNodes}
          edges={filteredEdges}
          traces={filteredTraces}
          agentPrompts={agentPrompts}
          selectedAgentId={selectedAgentId}
          onSelectAgent={onSelectAgent}
        />
      </section>

      <section
        className={`flex min-h-0 w-full shrink-0 flex-col overflow-hidden border-t border-[var(--nexus-rule-soft)] lg:w-[min(440px,42vw)] xl:w-[min(520px,38vw)] lg:border-l-2 lg:border-l-[var(--nexus-glow)]/28 lg:border-t-0 lg:min-h-0 ${
          selectedAgentId
            ? "max-h-[min(52vh,520px)] min-h-[min(40vh,360px)] lg:max-h-none lg:min-h-0"
            : "max-h-none lg:min-h-0"
        }`}
      >
        {selectedAgentId ? (
          <AgentDetailPanel
            nodeId={selectedAgentId}
            node={selectedAgentNodeFiltered ?? selectedAgentNode}
            traces={selectedAgentTracesFiltered.length ? selectedAgentTracesFiltered : selectedAgentTraces}
            promptDefaults={selectedAgentPromptFiltered ?? selectedAgentPrompt}
            loading={streaming}
            onClose={() => onSelectAgent(null)}
            variant="inline"
          />
        ) : (
          <>
            <div className="shrink-0 border-b border-[var(--nexus-border)]/60 px-4 py-2.5 text-center lg:hidden">
              <p className="text-[10px] text-slate-400">Select an agent.</p>
            </div>
            <div className="hidden min-h-[200px] flex-1 flex-col items-center justify-center gap-2 bg-[var(--nexus-panel)]/35 p-6 text-center lg:flex">
              <p className="text-xs font-medium text-slate-200">No agent selected</p>
              <p className="max-w-[200px] text-[10px] font-mono text-[var(--nexus-muted)]">
                Detail panel · empty
              </p>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
