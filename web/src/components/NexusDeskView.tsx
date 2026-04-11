"use client";

import { NexusStarSystem } from "@/components/NexusStarSystem";
import { NexusThoughtStreamPanel } from "@/components/NexusThoughtStreamPanel";
import { TopologyGraph } from "@/components/TopologyGraph";
import type { RefObject } from "react";
import type { MessageLogEntry, NexusTrace, TopologyEdge, TopologyNode } from "@/types/nexus-payload";

interface NexusDeskViewProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  signalCount: number;
  streaming: boolean;
  tracesToShow: NexusTrace[];
  messageLog?: MessageLogEntry[];
  streamRef: RefObject<HTMLDivElement>;
  setCardRef: (traceId: string, el: HTMLDivElement | null) => void;
  readyToReveal: boolean;
  revealDone: boolean;
  onIntroDone: () => void;
}

export function NexusDeskView({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  signalCount,
  streaming,
  tracesToShow,
  messageLog,
  streamRef,
  setCardRef,
  readyToReveal,
  revealDone,
  onIntroDone,
}: NexusDeskViewProps) {
  const activeStarId =
    selectedNodeId ?? nodes.find((n) => n.status === "ACTIVE")?.id ?? null;

  if (!revealDone) {
    return (
      <main className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_minmax(50vw,2fr)_1fr] gap-0 w-full overflow-hidden">
        <section className="nexus-panel rounded-none lg:rounded-r-lg border-r-0 lg:border-r border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden">
          <div className="shrink-0 px-3 py-2 border-b border-[var(--nexus-border)]">
            <h2 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Event stream · chain-of-thought & provenance · node_id / parent_id
            </h2>
          </div>
          <div className="flex-1 min-h-0 p-3">
          </div>
        </section>

        <section className="flex h-full items-center justify-center bg-[var(--nexus-bg)]/50 p-2 lg:p-4">
          <NexusStarSystem
            nodes={nodes}
            edges={edges}
            activeNodeId={activeStarId}
            signalCount={signalCount}
            readyToReveal={readyToReveal}
            onIntroDone={onIntroDone}
            playIntro
          />
        </section>

        <section className="nexus-panel rounded-none lg:rounded-l-lg border-l border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden">
          <div className="shrink-0 px-3 py-2 border-b border-[var(--nexus-border)]">
            <h2 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Topology · nodes & edges
            </h2>
          </div>
          <div className="flex-1 min-h-0 p-3">
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[1fr_minmax(50vw,2fr)_1fr] gap-0 w-full overflow-hidden">
      <NexusThoughtStreamPanel
        streaming={streaming}
        selectedNodeId={selectedNodeId}
        tracesToShow={tracesToShow}
        messageLog={messageLog}
        streamRef={streamRef}
        setCardRef={setCardRef}
      />

      <section className="flex items-center justify-center min-h-0 bg-[var(--nexus-bg)]/50 p-2 lg:p-4">
        <NexusStarSystem
          nodes={nodes}
          edges={edges}
          activeNodeId={activeStarId}
          signalCount={signalCount}
          readyToReveal={readyToReveal}
          onIntroDone={onIntroDone}
          playIntro={false}
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
