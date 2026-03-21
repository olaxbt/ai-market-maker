"use client";

import type { RefObject } from "react";
import { motion } from "framer-motion";
import { AgentTraceCard } from "@/components/AgentTraceCard";
import type { NexusTrace } from "@/types/nexus-payload";

interface NexusThoughtStreamPanelProps {
  streaming: boolean;
  selectedNodeId: string | null;
  tracesToShow: NexusTrace[];
  streamRef: RefObject<HTMLDivElement>;
  setCardRef: (traceId: string, el: HTMLDivElement | null) => void;
}

export function NexusThoughtStreamPanel({
  streaming,
  selectedNodeId,
  tracesToShow,
  streamRef,
  setCardRef,
}: NexusThoughtStreamPanelProps) {
  return (
    <section className="nexus-panel rounded-none lg:rounded-r-lg border-r-0 lg:border-r border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden">
      <div className="shrink-0 px-3 py-2 border-b border-[var(--nexus-border)]">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
          Event stream · chain-of-thought & provenance · node_id / parent_id
        </h2>
      </div>
      <div
        ref={streamRef}
        className="thought-stream flex-1 min-h-0 overflow-y-auto overflow-x-hidden p-3 space-y-3"
        role="log"
        aria-label="Agent thought process stream"
      >
        {streaming && (
          <motion.div
            animate={{ opacity: [0.5, 1, 0.5] }}
            transition={{ repeat: Infinity, duration: 1.2 }}
            className="text-[var(--nexus-muted)] text-xs font-mono"
          >
            Waiting for traces…
          </motion.div>
        )}
        {!streaming && tracesToShow.length === 0 && (
          <p className="text-[var(--nexus-muted)] text-xs">
            {selectedNodeId
              ? "No trace for this node."
              : "No traces. Run the pipeline or load mock data."}
          </p>
        )}
        {!streaming &&
          tracesToShow.map((trace, i) => (
            <div
              key={trace.trace_id}
              ref={(el) => setCardRef(trace.trace_id, el)}
              className={
                selectedNodeId && trace.node_id === selectedNodeId
                  ? "rounded-lg shadow-[0_0_0_1px_rgba(0,212,170,0.35)]"
                  : ""
              }
            >
              <AgentTraceCard trace={trace} index={i} />
            </div>
          ))}
      </div>
    </section>
  );
}
