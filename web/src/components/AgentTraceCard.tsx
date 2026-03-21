"use client";

import { motion } from "framer-motion";
import { Cpu, Activity, ShieldCheck } from "lucide-react";
import { formatTraceTime } from "@/lib/formatTraceTime";
import type { NexusTrace } from "@/types/nexus-payload";

/** Renders one `NexusTrace`: thought steps, optional formula, proposal, and risk status. */
interface AgentTraceCardProps {
  trace: NexusTrace;
  index?: number;
}

export function AgentTraceCard({ trace, index = 0 }: AgentTraceCardProps) {
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

  const formulaObj =
    formula != null && typeof formula === "object"
      ? (formula as { name?: string; latex?: string; computed?: string })
      : null;

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.35, delay: index * 0.06 }}
      className="mb-4 w-full bg-[var(--nexus-surface)] border border-[var(--nexus-border)] rounded-lg overflow-hidden shadow-xl font-mono"
    >
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--nexus-panel)] border-b border-[var(--nexus-border)]">
        <div className="flex items-center gap-2">
          <Cpu size={16} className="text-[var(--nexus-glow)]" />
          <span className="text-xs font-bold text-[var(--nexus-glow)] uppercase tracking-widest">
            {actor.role}
          </span>
        </div>
        <span className="text-[10px] text-[var(--nexus-muted)]">
          {formatTraceTime(timestamp)}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {parent_id && (
          <div className="text-[10px] text-[var(--nexus-muted)]">
            ← parent: <code className="text-[var(--nexus-glow)]/80">{parent_id}</code>
          </div>
        )}

        <div className="space-y-2.5 rounded-md bg-[var(--nexus-bg)]/30 px-3 py-2.5">
          <div className="text-[9px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">
            Thought chain
          </div>
          {Array.isArray(thought_process) &&
            thought_process.map((step, idx) => (
              <div key={idx} className="flex gap-2.5">
                <span className="shrink-0 font-mono text-[10px] tabular-nums text-[var(--nexus-muted)]">
                  [{step.step}]
                </span>
                <div className="min-w-0">
                  <span className="font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--nexus-text)]">
                    {step.label}
                  </span>
                  <p className="mt-0.5 font-mono text-[10px] leading-snug text-slate-300">
                    {step.detail}
                  </p>
                </div>
              </div>
            ))}
        </div>

        {signalVal != null && (
          <div className="text-[10px]">
            <span className="text-[var(--nexus-muted)]">Signal:</span>{" "}
            <span className="text-[var(--nexus-glow)]">{String(signalVal)}</span>
            {confidenceVal != null && (
              <span className="text-[var(--nexus-muted)] ml-1">
                ({(Number(confidenceVal) * 100).toFixed(0)}%)
              </span>
            )}
          </div>
        )}

        {formulaObj && (formulaObj.latex ?? formulaObj.computed ?? formulaObj.name) && (
          <div className="bg-[var(--nexus-glow)]/10 border border-[var(--nexus-glow)]/30 p-3 rounded text-center">
            <div className="text-[10px] text-[var(--nexus-glow)]/80 uppercase mb-1">
              Active Logic Formula
            </div>
            {formulaObj.latex && (
              <code className="text-[var(--nexus-glow)] text-sm block break-all">
                {formulaObj.latex}
              </code>
            )}
            {formulaObj.computed && (
              <div className="text-xs text-[var(--nexus-muted)] mt-1">{formulaObj.computed}</div>
            )}
          </div>
        )}

        {formula != null && typeof formula === "string" && (
          <div className="bg-[var(--nexus-glow)]/10 border border-[var(--nexus-glow)]/30 p-3 rounded text-[10px] text-[var(--nexus-muted)]">
            {formula}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mt-4">
          {proposal && (
            <div className="bg-[var(--nexus-panel)] p-3 rounded border border-[var(--nexus-border)]">
              <div className="flex items-center gap-2 mb-1">
                <Activity size={14} className="text-[var(--nexus-success)]" />
                <span className="text-[10px] text-[var(--nexus-muted)] uppercase">Proposal</span>
              </div>
              <div className="text-xs font-bold text-[var(--nexus-success)]">
                {proposal.action}{" "}
                {proposal.params?.amount != null && (
                  <>
                    {String(proposal.params.amount)}
                    {proposal.params?.unit != null ? ` ${String(proposal.params.unit)}` : ""}
                  </>
                )}
              </div>
              {(proposal.params?.price != null || proposal.params?.leverage != null) && (
                <div className="text-[10px] text-[var(--nexus-muted)] mt-1">
                  {proposal.params?.price != null && `Price: $${proposal.params.price}`}
                  {proposal.params?.leverage != null &&
                    `${proposal.params?.price != null ? " | " : ""}Lev: ${String(proposal.params.leverage)}`}
                </div>
              )}
            </div>
          )}

          {veto_status && (
            <div
              className={`p-3 rounded border ${
                veto_status.status === "APPROVED"
                  ? "bg-[var(--nexus-success)]/10 border-[var(--nexus-success)]/40"
                  : "bg-[var(--nexus-danger)]/10 border-[var(--nexus-danger)]/40"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <ShieldCheck
                  size={14}
                  className={
                    veto_status.status === "APPROVED"
                      ? "text-[var(--nexus-success)]"
                      : "text-[var(--nexus-danger)]"
                  }
                />
                <span className="text-[10px] text-[var(--nexus-muted)] uppercase">Risk Status</span>
              </div>
              <div
                className={`text-xs font-bold ${
                  veto_status.status === "APPROVED"
                    ? "text-[var(--nexus-success)]"
                    : "text-[var(--nexus-danger)]"
                }`}
              >
                {veto_status.status}
              </div>
              {veto_status.reason && (
                <div className="text-[9px] text-[var(--nexus-muted)] mt-1 leading-tight">
                  {veto_status.reason}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="h-0.5 w-full bg-gradient-to-r from-transparent via-[var(--nexus-glow)]/20 to-transparent animate-pulse" />
    </motion.div>
  );
}
