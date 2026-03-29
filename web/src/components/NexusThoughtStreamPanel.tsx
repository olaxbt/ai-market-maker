"use client";

import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { AgentTraceCard } from "@/components/AgentTraceCard";
import type { NexusTrace } from "@/types/nexus-payload";

interface NexusThoughtStreamPanelProps {
  streaming: boolean;
  selectedNodeId: string | null;
  tracesToShow: NexusTrace[];
  streamRef: RefObject<HTMLDivElement>;
  setCardRef: (traceId: string, el: HTMLDivElement | null) => void;
  /** Merged onto outer section (e.g. backtest right rail: full height, no extra chrome). */
  className?: string;
  /** Disable staggered card enter animation (backtest verbose mode). */
  reduceMotion?: boolean;
}

export function NexusThoughtStreamPanel({
  streaming,
  selectedNodeId,
  tracesToShow,
  streamRef,
  setCardRef,
  className,
  reduceMotion = false,
}: NexusThoughtStreamPanelProps) {
  const [unseenCount, setUnseenCount] = useState(0);
  const stickToBottomRef = useRef(true);
  const prevTraceCountRef = useRef(0);

  const scrollToBottom = (behavior: ScrollBehavior = "smooth") => {
    const el = streamRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  };

  useEffect(() => {
    const el = streamRef.current;
    if (!el) return;

    const NEAR_BOTTOM_PX = 120;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      const nearBottom = distance <= NEAR_BOTTOM_PX;
      stickToBottomRef.current = nearBottom;
      if (nearBottom) setUnseenCount(0);
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    // Initialize pinned state.
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, [streamRef]);

  useEffect(() => {
    const prev = prevTraceCountRef.current;
    const next = tracesToShow.length;
    if (next <= prev) {
      prevTraceCountRef.current = next;
      return;
    }

    const newItems = next - prev;
    prevTraceCountRef.current = next;

    if (stickToBottomRef.current) {
      // Wait a tick so the new cards mount and height is updated.
      window.setTimeout(() => scrollToBottom("auto"), 0);
      setUnseenCount(0);
      return;
    }

    setUnseenCount((c) => c + newItems);
  }, [tracesToShow.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const hasTraces = tracesToShow.length > 0;

  return (
    <section
      className={
        className ??
        "nexus-panel rounded-none lg:rounded-r-lg border-r-0 lg:border-r border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden"
      }
    >
      <div className="shrink-0 px-3 py-2 border-b border-[var(--nexus-border)]">
        <h2 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
          Event stream · chain-of-thought & provenance · node_id / parent_id
        </h2>
      </div>
      <div className="relative flex-1 min-h-0 overflow-hidden">
        <div
          ref={streamRef}
          className="thought-stream h-full overflow-y-auto overflow-x-hidden p-3 space-y-3"
          role="log"
          aria-label="Agent thought process stream"
        >
          {streaming && !hasTraces && (
            <motion.div
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ repeat: Infinity, duration: 1.2 }}
              className="text-[var(--nexus-muted)] text-xs font-mono"
            >
              Waiting for traces…
            </motion.div>
          )}
          {!streaming && !hasTraces && (
            <p className="text-[var(--nexus-muted)] text-xs">
              {selectedNodeId
                ? "No trace for this node."
                : "No traces. Run the pipeline or load mock data."}
            </p>
          )}
          {hasTraces &&
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
                <AgentTraceCard trace={trace} index={i} reduceMotion={reduceMotion} />
              </div>
            ))}
          {streaming && hasTraces ? (
            <p className="text-[10px] font-mono text-[var(--nexus-glow)]/80">
              Live · trace stream updating as bars complete
            </p>
          ) : null}
        </div>

        {unseenCount > 0 ? (
          <div className="pointer-events-none absolute inset-x-0 bottom-2 flex justify-center px-3">
            <button
              type="button"
              onClick={() => {
                stickToBottomRef.current = true;
                scrollToBottom("smooth");
                setUnseenCount(0);
              }}
              className="pointer-events-auto rounded-full border border-[var(--nexus-glow)]/35 bg-[var(--nexus-panel)]/90 px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-glow)] backdrop-blur hover:border-[var(--nexus-glow)]/60"
            >
              New events ({unseenCount}) ↓
            </button>
          </div>
        ) : null}
      </div>
    </section>
  );
}
