"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentsConsoleView } from "@/components/AgentsConsoleView";
import { NexusConsoleHeader, type NexusViewMode } from "@/components/NexusConsoleHeader";
import { NexusDeskView } from "@/components/NexusDeskView";
import { useNexusPayload } from "@/hooks/useNexusPayload";
import { useNexusSignalCount } from "@/hooks/useNexusSignalCount";
import type { Topology } from "@/types/nexus-payload";

const EMPTY_TOPOLOGY: Topology = { nodes: [], edges: [] };

export default function NexusPage() {
  const { payload, loading: streaming, error: loadError } = useNexusPayload();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<NexusViewMode>("nexus");
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const metadata = payload?.metadata ?? null;
  const topology = useMemo(
    () => payload?.topology ?? EMPTY_TOPOLOGY,
    [payload?.topology],
  );
  const traces = useMemo(() => payload?.traces ?? [], [payload?.traces]);

  const signalCount = useNexusSignalCount(payload?.message_log, traces.length);

  const tracesToShow = useMemo(() => {
    if (!selectedNodeId) return traces;
    return traces.filter((t) => t.node_id === selectedNodeId);
  }, [traces, selectedNodeId]);

  const selectedAgentTraces = useMemo(
    () => (selectedAgentId ? traces.filter((t) => t.node_id === selectedAgentId) : []),
    [traces, selectedAgentId],
  );
  const selectedAgentNode = useMemo(
    () =>
      selectedAgentId ? topology.nodes.find((n) => n.id === selectedAgentId) ?? null : null,
    [topology.nodes, selectedAgentId],
  );

  const selectedAgentPrompt = useMemo(() => {
    const rows = payload?.agent_prompts;
    if (!selectedAgentId || !rows?.length) return null;
    return rows.find((p) => p.node_id === selectedAgentId) ?? null;
  }, [payload?.agent_prompts, selectedAgentId]);

  useEffect(() => {
    if (viewMode !== "grid") setSelectedAgentId(null);
  }, [viewMode]);

  const viewModeTitle =
    viewMode === "nexus"
      ? "Nexus: live topology, event stream, and mesh."
      : "Agents: pick a card; detail, traces, and prompts open in the side panel (same page).";

  const setCardRef = useCallback((traceId: string, el: HTMLDivElement | null) => {
    if (el) cardRefs.current.set(traceId, el);
    else cardRefs.current.delete(traceId);
  }, []);

  useEffect(() => {
    if (!selectedNodeId || tracesToShow.length === 0) return;
    const first = tracesToShow[0];
    const el = first && cardRefs.current.get(first.trace_id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [selectedNodeId, tracesToShow]);

  return (
    <div className="min-h-screen flex flex-col nexus-bg lg:h-screen lg:min-h-0 lg:overflow-hidden">
      <NexusConsoleHeader
        metadata={metadata}
        viewMode={viewMode}
        onViewModeChange={setViewMode}
        viewModeTitle={viewModeTitle}
      />

      {loadError && !streaming ? (
        <div
          className="shrink-0 border-b border-[var(--nexus-danger)]/40 bg-[var(--nexus-danger)]/10 px-4 py-2 text-center font-mono text-[11px] text-[var(--nexus-danger)]"
          role="alert"
        >
          Failed to load traces: {loadError.message}
        </div>
      ) : null}

      {viewMode === "grid" ? (
        <AgentsConsoleView
          nodes={topology.nodes}
          edges={topology.edges}
          traces={traces}
          agentPrompts={payload?.agent_prompts}
          selectedAgentId={selectedAgentId}
          onSelectAgent={setSelectedAgentId}
          selectedAgentTraces={selectedAgentTraces}
          selectedAgentNode={selectedAgentNode}
          selectedAgentPrompt={selectedAgentPrompt}
          streaming={streaming}
        />
      ) : (
        <NexusDeskView
          nodes={topology.nodes}
          edges={topology.edges}
          selectedNodeId={selectedNodeId}
          onSelectNode={setSelectedNodeId}
          signalCount={signalCount}
          streaming={streaming}
          tracesToShow={tracesToShow}
          streamRef={streamRef}
          setCardRef={setCardRef}
        />
      )}

      <footer className="border-t border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/80 px-4 py-2 text-[10px] text-[var(--nexus-muted)] font-mono">
        metadata + topology + traces (node_id, parent_id) · streaming chain-of-thought and decision provenance
      </footer>
    </div>
  );
}
