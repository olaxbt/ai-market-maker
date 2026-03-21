"use client";

import { motion } from "framer-motion";
import { formatTraceTime } from "@/lib/formatTraceTime";
import type { AgentTrace } from "@/types/agent-trace";

interface AgentThoughtCardProps {
  trace: AgentTrace;
  index?: number;
}

export function AgentThoughtCard({ trace, index = 0 }: AgentThoughtCardProps) {
  const { actor, timestamp, thought_process, proposal, veto_status } = trace;
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
      <div className="flex justify-between items-center mb-2">
        <span className="text-[var(--nexus-glow)] font-bold">[{actor.role}]</span>
        <span className="text-[var(--nexus-muted)] text-[10px]">{formatTraceTime(timestamp)}</span>
      </div>

      <div className="space-y-1.5 text-[var(--nexus-text)]">
        {thought_process.map((t, i) => (
          <div key={i} className="flex gap-2">
            <span className="text-[var(--nexus-glow)]/70 shrink-0">➜</span>
            <p>{t.detail}</p>
          </div>
        ))}
      </div>

      {proposal && (
        <div className="mt-3 p-2 bg-[var(--nexus-panel)] rounded border border-[var(--nexus-border)]">
          <div className="text-[10px] text-[var(--nexus-muted)] uppercase">Proposal</div>
          <div className="text-[var(--nexus-success)] font-bold">
            {proposal.action}{" "}
            {typeof proposal.params?.amount === "number" && (
              <>
                {proposal.params.amount} {String(proposal.params?.unit ?? "")} @{" "}
                {typeof proposal.params?.price === "number" && proposal.params.price}
              </>
            )}
            {!proposal.params?.amount &&
              proposal.params &&
              Object.keys(proposal.params).length > 0 &&
              JSON.stringify(proposal.params)}
          </div>
        </div>
      )}

      {veto_status && (
        <div className={`mt-2 px-2 py-1 rounded border text-[10px] ${vetoColor}`}>
          <span className="font-semibold">{veto_status.checked_by}</span>: {veto_status.status}
          {veto_status.reason && (
            <span className="block text-slate-500 mt-0.5">{veto_status.reason}</span>
          )}
        </div>
      )}
    </motion.div>
  );
}
