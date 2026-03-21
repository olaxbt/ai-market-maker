"use client";

import { NexusStarSystem } from "@/components/NexusStarSystem";
import { NexusThoughtStreamPanel } from "@/components/NexusThoughtStreamPanel";
import { TopologyGraph } from "@/components/TopologyGraph";
import type { RefObject } from "react";
import type { NexusTrace, TopologyEdge, TopologyNode } from "@/types/nexus-payload";

interface NexusDeskViewProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  signalCount: number;
  streaming: boolean;
  tracesToShow: NexusTrace[];
  streamRef: RefObject<HTMLDivElement>;
  setCardRef: (traceId: string, el: HTMLDivElement | null) => void;
}

export function NexusDeskView({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  signalCount,
  streaming,
  tracesToShow,
  streamRef,
  setCardRef,
}: NexusDeskViewProps) {
  const activeStarId =
    selectedNodeId ?? nodes.find((n) => n.status === "ACTIVE")?.id ?? null;

  return (
    <main className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_minmax(50vw,2fr)_1fr] gap-0 w-full overflow-hidden">
      <NexusThoughtStreamPanel
        streaming={streaming}
        selectedNodeId={selectedNodeId}
        tracesToShow={tracesToShow}
        streamRef={streamRef}
        setCardRef={setCardRef}
      />

      <section className="flex items-center justify-center min-h-0 bg-[var(--nexus-bg)]/50 p-2 lg:p-4">
        <NexusStarSystem
          nodes={nodes}
          edges={edges}
          activeNodeId={activeStarId}
          signalCount={signalCount}
        />
      </section>

      <section className="nexus-panel rounded-none lg:rounded-l-lg border-l border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden">
        <div className="flex-1 min-h-0 overflow-y-auto p-3">
          <TopologyGraph
            nodes={nodes}
            edges={edges}
            selectedNodeId={selectedNodeId}
            onSelectNode={onSelectNode}
          />
        </div>
      </section>
    </main>
  );
}
