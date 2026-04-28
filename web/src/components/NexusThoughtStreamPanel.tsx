"use client";

import type { RefObject } from "react";
import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { AgentTraceCard } from "@/components/AgentTraceCard";
import type { MessageLogEntry, NexusTrace } from "@/types/nexus-payload";

interface NexusThoughtStreamPanelProps {
  streaming: boolean;
  selectedNodeId: string | null;
  tracesToShow: NexusTrace[];
  messageLog?: MessageLogEntry[];
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
  messageLog,
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
  const renderTraces = hasTraces ? tracesToShow.slice(-350) : tracesToShow;
  // `selectedNodeId` is the topology node id (e.g. "n11"), not the actor string.
  const filteredLog = (messageLog ?? []).filter((m) =>
    selectedNodeId ? m.node_id === selectedNodeId : true,
  );
  const logToShow = filteredLog.slice(-120);

  return (
    <section
      className={
        className ??
        "nexus-panel rounded-none lg:rounded-r-lg border-r-0 lg:border-r border-[var(--nexus-border)] flex flex-col min-h-0 overflow-hidden"
      }
    >
      <div className="relative flex-1 min-h-0 overflow-hidden">
        <div
          ref={streamRef}
          className="thought-stream h-full overflow-y-auto overflow-x-hidden"
          role="log"
          aria-label="Agent thought process stream"
        >
          <div className="sticky top-0 z-10 border-b border-[var(--nexus-border)] bg-[var(--nexus-panel)]/95 px-3 py-2 backdrop-blur">
            <h2 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Event stream · chain-of-thought & provenance · node_id / parent_id
            </h2>
          </div>
          <div className="p-3 space-y-3">
            {streaming && !hasTraces && (
              <motion.div
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ repeat: Infinity, duration: 1.2 }}
                className="text-[var(--nexus-muted)] text-xs font-mono"
              >
                Waiting for traces…
              </motion.div>
            )}
            {logToShow.length > 0 ? (
              <div className="space-y-2">
                <div className="text-[10px] font-mono uppercase tracking-widest text-[var(--nexus-muted)]">
                  Recent events
                </div>
                <div className="space-y-1.5">
                  {logToShow.map((m) => (
                    <div
                      key={m.seq}
                      className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/70 px-3 py-2 font-mono text-[11px] text-[var(--nexus-text)]"
                    >
                      <div className="flex items-center justify-between gap-2 text-[10px] text-[var(--nexus-muted)]">
                        <span className="truncate">
                          {m.actor_id} · {m.kind}
                        </span>
                        <span className="tabular-nums">{new Date(m.ts).toLocaleTimeString()}</span>
                      </div>
                      <div className="mt-1 whitespace-pre-wrap break-words">{m.message}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            {!streaming && !hasTraces && (
              <p className="text-[var(--nexus-muted)] text-xs">
                {selectedNodeId
                  ? "No trace for this node."
                  : "No traces. Run the pipeline or load mock data."}
              </p>
            )}
            {hasTraces &&
              renderTraces.map((trace, i) => (
                <div
                  key={trace.trace_id}
                  ref={(el) => setCardRef(trace.trace_id, el)}
                  className={
                    selectedNodeId && trace.node_id === selectedNodeId
                      ? "rounded-lg shadow-[0_0_0_1px_rgba(0,212,170,0.35)]"
                      : ""
                  }
                >
                  <AgentTraceCard
                    trace={trace}
                    index={i}
                    // Live updates look bad if every new card animates.
                    reduceMotion={reduceMotion || streaming}
                  />
                </div>
              ))}
            {streaming && hasTraces ? (
              <p className="text-[10px] font-mono text-[var(--nexus-glow)]/80">
                Live · trace stream updating as bars complete
              </p>
            ) : null}
          </div>
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
