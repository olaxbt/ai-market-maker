"use client";

import { motion } from "framer-motion";
import { useMemo } from "react";
import { topologyLayers } from "@/lib/topologyLayers";
import type { TopologyNode, TopologyEdge } from "@/types/nexus-payload";

interface TopologyGraphProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
}

const statusColors = {
  COMPLETED: "border-[color:var(--nexus-topology-idle-border)] text-[var(--nexus-success)]",
  ACTIVE: "border-[var(--nexus-glow)]/65 text-[var(--nexus-glow)] flow-node-active",
  PENDING: "border-[color:var(--nexus-topology-idle-border)] text-[var(--nexus-muted)]",
};

function runtimeStatusLabel(status: TopologyNode["status"]): string {
  if (status === "ACTIVE") return "RUNNING";
  if (status === "COMPLETED") return "COMPLETED";
  return "STANDBY";
}

function NodeTile({
  node,
  selected,
  onSelect,
  delayIndex,
}: {
  node: TopologyNode;
  selected: boolean;
  onSelect: () => void;
  delayIndex: number;
}) {
  const statusClass = statusColors[node.status] ?? statusColors.PENDING;
  return (
    <motion.button
      type="button"
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: delayIndex * 0.03 }}
      onClick={onSelect}
      className={`
        text-left px-2.5 py-2 rounded font-mono text-[11px] border transition-all duration-200
        min-w-0 flex-1 basis-[calc(50%-0.25rem)] sm:basis-[calc(33.333%-0.25rem)]
        outline-none focus-visible:shadow-[0_0_0_2px_rgba(0,212,170,0.35)]
        ${selected ? "flow-node-active bg-[var(--nexus-surface)] border-[var(--nexus-glow)] text-[var(--nexus-glow)]" : ""}
        ${!selected ? `${statusClass} bg-[var(--nexus-surface)]/80 hover:border-[var(--nexus-glow)]/35` : ""}
      `}
    >
      <span className="block font-medium leading-tight">{node.label}</span>
      <span className="block text-[9px] text-[var(--nexus-muted)] mt-0.5">
        {runtimeStatusLabel(node.status)}
      </span>
    </motion.button>
  );
}

export function TopologyGraph({ nodes, edges, selectedNodeId, onSelectNode }: TopologyGraphProps) {
  const layers = useMemo(() => topologyLayers(nodes, edges), [nodes, edges]);

  return (
    <div className="flex flex-col">
      <div className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)] mb-3">
        Topology · nodes & edges
      </div>
      <div className="relative flex flex-col gap-1">
        {layers.map((row, layerIdx) => (
          <div key={`layer-${layerIdx}`} className="flex flex-col gap-1">
            <div className="flex items-center gap-2 px-0.5">
              <span className="text-[9px] font-mono uppercase tracking-wider text-[var(--nexus-muted)]">
                Stage {layerIdx + 1}
                {row.length > 1 ? ` · ${row.length} parallel` : ""}
              </span>
            </div>
            <div className="flex flex-wrap gap-2">
              {row.map((node, i) => {
                const isSelected = selectedNodeId === node.id;
                return (
                  <NodeTile
                    key={node.id}
                    node={node}
                    selected={isSelected}
                    delayIndex={layerIdx * 8 + i}
                    onSelect={() => onSelectNode(isSelected ? null : node.id)}
                  />
                );
              })}
            </div>
            {layerIdx < layers.length - 1 && (
              <div className="flex justify-center py-1">
                <span className="text-[var(--nexus-muted)]/50 text-lg leading-none">↓</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
