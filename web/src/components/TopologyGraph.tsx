"use client";

import { motion } from "framer-motion";
import type { TopologyNode, TopologyEdge } from "@/types/nexus-payload";

interface TopologyGraphProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
}

const statusColors = {
  /* Idle frame uses shared token so STANDBY isn’t “borderless” vs the hub frame */
  COMPLETED: "border-[color:var(--nexus-topology-idle-border)] text-[var(--nexus-success)]",
  ACTIVE: "border-[var(--nexus-glow)]/65 text-[var(--nexus-glow)] flow-node-active",
  PENDING: "border-[color:var(--nexus-topology-idle-border)] text-[var(--nexus-muted)]",
};

function runtimeStatusLabel(status: TopologyNode["status"]): string {
  if (status === "ACTIVE") return "RUNNING";
  if (status === "COMPLETED") return "MONITORING";
  return "STANDBY";
}

export function TopologyGraph({ nodes, edges, selectedNodeId, onSelectNode }: TopologyGraphProps) {
  return (
    <div className="flex flex-col">
      <div className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)] mb-3">
        Topology · nodes & edges
      </div>
      <div className="relative flex flex-col gap-2">
        {nodes.map((node, i) => {
          const isSelected = selectedNodeId === node.id;
          const statusClass = statusColors[node.status] ?? statusColors.PENDING;
          const isLast = i === nodes.length - 1;
          return (
            <div key={node.id} className="flex flex-col gap-0">
              <motion.button
                type="button"
                initial={{ opacity: 0, x: 8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                onClick={() => onSelectNode(isSelected ? null : node.id)}
                className={`
                  text-left px-3 py-2 rounded font-mono text-xs border transition-all duration-200 w-full
                  outline-none focus-visible:shadow-[0_0_0_2px_rgba(0,212,170,0.35)]
                  ${isSelected ? "flow-node-active bg-[var(--nexus-surface)] border-[var(--nexus-glow)] text-[var(--nexus-glow)]" : ""}
                  ${!isSelected ? `${statusClass} bg-[var(--nexus-surface)]/80 hover:border-[var(--nexus-glow)]/35` : ""}
                `}
              >
                <span className="block font-medium">{node.label}</span>
                <span className="block text-[10px] text-[var(--nexus-muted)] mt-0.5">{runtimeStatusLabel(node.status)}</span>
              </motion.button>
              {!isLast && edges.some((e) => e.from === node.id) && (
                <div className="flex justify-center py-0.5">
                  <span className="text-[var(--nexus-muted)]/50 text-lg leading-none">↓</span>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
