"use client";

import { motion } from "framer-motion";
import { formatTraceTime } from "@/lib/formatTraceTime";
import type { NexusTrace } from "@/types/nexus-payload";

interface NexusThoughtCardProps {
  trace: NexusTrace;
  index?: number;
}

export function NexusThoughtCard({ trace, index = 0 }: NexusThoughtCardProps) {
  const { actor, timestamp, content, parent_id } = trace;
  const {
    thought_process = [],
    signal,
    confidence,
    formula,
    proposal,
    veto_status,
    context,
  } = content ?? {};
  const signalVal =
    signal ??
    (context && typeof context === "object" && "signal" in context
      ? (context as { signal?: string }).signal
      : undefined);
  const confidenceVal =
    confidence ??
    (context && typeof context === "object" && "confidence" in context
      ? (context as { confidence?: number }).confidence
      : undefined);

  const vetoColor =
    veto_status?.status === "APPROVED"
      ? "border-[var(--nexus-success)]/60 text-[var(--nexus-success)]"
      : veto_status?.status === "REJECTED"
        ? "border-[var(--nexus-danger)]/60 text-[var(--nexus-danger)]"
        : "border-[var(--nexus-border)]";

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.3, delay: index * 0.06 }}
      className="bg-[var(--nexus-surface)] border-l-4 border-[var(--nexus-glow)] p-3 font-mono text-xs rounded-r shadow-lg"
    >
      <div className="flex justify-between items-center mb-2 flex-wrap gap-1">
        <span className="text-[var(--nexus-glow)] font-bold">[{actor.role}]</span>
        <span className="text-[var(--nexus-muted)] text-[10px]">{formatTraceTime(timestamp)}</span>
      </div>
      {parent_id && (
        <div className="text-[10px] text-[var(--nexus-muted)] mb-1.5">
          ← parent: <code className="text-[var(--nexus-glow)]/80">{parent_id}</code>
        </div>
      )}

      <div className="space-y-1.5 text-[var(--nexus-text)]">
        {Array.isArray(thought_process) &&
          thought_process.map((t, i) => (
            <div key={i} className="flex gap-2">
              <span className="text-[var(--nexus-glow)]/70 shrink-0">➜</span>
              <p>{t.detail}</p>
            </div>
          ))}
      </div>

      {signalVal != null && (
        <div className="mt-2 text-[10px]">
          <span className="text-[var(--nexus-muted)]">Signal:</span>{" "}
          <span className="text-[var(--nexus-glow)]">{String(signalVal)}</span>
          {confidenceVal != null && (
            <span className="text-[var(--nexus-muted)] ml-1">
              ({(Number(confidenceVal) * 100).toFixed(0)}%)
            </span>
          )}
        </div>
      )}

      {formula != null && (
        <div className="mt-2 p-1.5 bg-[var(--nexus-panel)] rounded border border-[var(--nexus-border)] text-[10px] text-[var(--nexus-muted)]">
          {typeof formula === "string"
            ? formula
            : ((formula as { name?: string; latex?: string; computed?: string })?.computed ??
              (formula as { name?: string }).name ??
              JSON.stringify(formula))}
        </div>
      )}

      {proposal && (
        <div className="mt-3 p-2 bg-[var(--nexus-panel)] rounded border border-[var(--nexus-border)]">
          <div className="text-[10px] text-[var(--nexus-muted)] uppercase">Proposal</div>
          <div className="text-[var(--nexus-success)] font-bold">
            {proposal.action}{" "}
            {typeof proposal.params?.amount === "number" && (
              <>
                {proposal.params.amount}
                {proposal.params?.unit != null ? ` ${String(proposal.params.unit)}` : ""}
                {typeof proposal.params?.price === "number" ? ` @ ${proposal.params.price}` : ""}
              </>
            )}
            {typeof proposal.params?.amount !== "number" &&
              proposal.params &&
              Object.keys(proposal.params).length > 0 &&
              JSON.stringify(proposal.params)}
          </div>
        </div>
      )}

      {veto_status && (
        <div className={`mt-2 px-2 py-1 rounded border text-[10px] ${vetoColor}`}>
          {veto_status.checked_by != null && (
            <span className="font-semibold">{veto_status.checked_by}: </span>
          )}
          {veto_status.status}
          {veto_status.reason && (
            <span className="block text-[var(--nexus-muted)] mt-0.5">{veto_status.reason}</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
