"use client";

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
  return (
    <main className="flex flex-1 min-h-0 w-full flex-col overflow-hidden lg:flex-row lg:items-stretch">
      <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <AgentGridView
          nodes={nodes}
          edges={edges}
          traces={traces}
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
            node={selectedAgentNode}
            traces={selectedAgentTraces}
            promptDefaults={selectedAgentPrompt}
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
