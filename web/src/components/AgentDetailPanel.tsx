"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { RotateCcw, SlidersHorizontal } from "lucide-react";
import { AgentTraceCard } from "@/components/AgentTraceCard";
import type { AgentPromptSettings, NexusTrace, TopologyNode } from "@/types/nexus-payload";
import { agentAvatarStaticSrc } from "@/lib/agentAvatars";

export interface AgentDetailPanelProps {
  nodeId: string;
  node: TopologyNode | null;
  traces: NexusTrace[];
  /** Hydrate from `NexusPayload.agent_prompts` (demo / API). */
  promptDefaults?: AgentPromptSettings | null;
  loading?: boolean;
  onClose?: () => void;
  variant?: "inline" | "page";
}

function runtimeStatusLabel(status: TopologyNode["status"] | undefined): string {
  if (status === "ACTIVE") return "RUNNING";
  if (status === "COMPLETED") return "MONITORING";
  if (status === "PENDING") return "STANDBY";
  return "UNKNOWN";
}

export function AgentDetailPanel({
  nodeId,
  node,
  traces,
  promptDefaults = null,
  loading = false,
  onClose,
  variant = "inline",
}: AgentDetailPanelProps) {
  type PromptSnapshot = { system: string; task: string };
  const [systemPrompt, setSystemPrompt] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [savedSnapshot, setSavedSnapshot] = useState<PromptSnapshot | null>(null);
  const [saveAck, setSaveAck] = useState(false);
  const cotEnabled = !!promptDefaults?.cot_enabled;

  useEffect(() => {
    if (promptDefaults) {
      setSystemPrompt(promptDefaults.system_prompt);
      setTaskPrompt(promptDefaults.task_prompt);
      setSavedSnapshot({
        system: promptDefaults.system_prompt,
        task: promptDefaults.task_prompt,
      });
    } else {
      setSystemPrompt("");
      setTaskPrompt("");
      setSavedSnapshot({ system: "", task: "" });
    }
    setSaveAck(false);
  }, [nodeId, promptDefaults]);

  const promptDirty = useMemo(() => {
    const baseline = savedSnapshot ?? {
      system: promptDefaults?.system_prompt ?? "",
      task: promptDefaults?.task_prompt ?? "",
    };
    return systemPrompt !== baseline.system || taskPrompt !== baseline.task;
  }, [savedSnapshot, promptDefaults, systemPrompt, taskPrompt]);

  const resetPromptsFromPayload = () => {
    if (!promptDefaults) return;
    setSystemPrompt(promptDefaults.system_prompt);
    setTaskPrompt(promptDefaults.task_prompt);
    setSavedSnapshot({
      system: promptDefaults.system_prompt,
      task: promptDefaults.task_prompt,
    });
    setSaveAck(false);
  };
  const savePromptsMock = () => {
    setSavedSnapshot({ system: systemPrompt, task: taskPrompt });
    setSaveAck(true);
    setTimeout(() => setSaveAck(false), 1600);
  };
  const runtimeLabel = runtimeStatusLabel(node?.status);
  const avatarBorder =
    runtimeLabel === "RUNNING"
      ? "border-emerald-300/55"
      : runtimeLabel === "MONITORING"
        ? "border-cyan-200/45"
        : "border-slate-400/45";

  return (
    <div className="flex h-full min-h-0 flex-col bg-[var(--nexus-panel)]/95">
      <div className="shrink-0 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-surface)]/35 px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <div
              className={`relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border ${avatarBorder}`}
              aria-hidden
            >
              <Image
                src={agentAvatarStaticSrc(nodeId)}
                alt=""
                fill
                className="object-cover opacity-92"
              />
            </div>

            <div className="min-w-0 flex-1 flex flex-col gap-1">
              <span className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]">
                {variant === "inline" ? "Agent detail" : "Agent"}
              </span>
              <h2 className="break-words font-mono text-sm font-semibold leading-snug text-[var(--nexus-glow)] nexus-glow-text">
                {node?.label ?? nodeId}
              </h2>
              <p className="break-words font-mono text-[10px] leading-relaxed text-slate-300">
                <span className="text-[var(--nexus-muted)]">node_id</span>{" "}
                <span className="text-[var(--nexus-text)]">{nodeId}</span>
                {node?.actor ? (
                  <>
                    {" "}
                    <span className="text-[var(--nexus-muted)]">· actor</span>{" "}
                    <span className="text-[var(--nexus-text)]">{node.actor}</span>
                  </>
                ) : null}
                {node?.status ? (
                  <>
                    {" "}
                    <span className="text-[var(--nexus-muted)]">· status</span>{" "}
                    <span className="text-[var(--nexus-glow)]">{runtimeLabel}</span>
                  </>
                ) : null}
              </p>
            </div>
          </div>
          {variant === "inline" && onClose ? (
            <button
              type="button"
              onClick={onClose}
              className="shrink-0 rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/80 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest text-slate-200 hover:border-[var(--nexus-glow)]/50"
            >
              Close
            </button>
          ) : null}
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="space-y-6 p-4">
          {promptDefaults && (promptDefaults.model != null || (promptDefaults.tools?.length ?? 0) > 0) ? (
            <section className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/50 p-3">
              <div className="text-[10px] uppercase tracking-widest text-[var(--nexus-muted)] mb-2">Model & tools</div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 font-mono text-[10px] text-slate-300">
                {promptDefaults.model != null ? (
                  <span>
                    <span className="text-[var(--nexus-muted)]">model</span> {promptDefaults.model}
                  </span>
                ) : null}
                {promptDefaults.temperature != null ? (
                  <span>
                    <span className="text-[var(--nexus-muted)]">temp</span> {promptDefaults.temperature}
                  </span>
                ) : null}
                {promptDefaults.max_tokens != null ? (
                  <span>
                    <span className="text-[var(--nexus-muted)]">max_tokens</span> {promptDefaults.max_tokens}
                  </span>
                ) : null}
              </div>
              {promptDefaults.tools && promptDefaults.tools.length > 0 ? (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {promptDefaults.tools.map((t) => (
                    <span
                      key={t}
                      className="rounded border border-[var(--nexus-glow)]/25 bg-[var(--nexus-bg)]/80 px-2 py-0.5 font-mono text-[9px] text-[var(--nexus-glow)]/95"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              ) : null}
            </section>
          ) : null}

          <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/20 p-4">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-2.5">
                <SlidersHorizontal className="mt-0.5 h-4 w-4 shrink-0 text-[var(--nexus-glow)]" aria-hidden />
                <div>
                  <h3 className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--nexus-glow)]">
                    Prompt configuration
                  </h3>
                  <p className="mt-1 max-w-prose text-[10px] leading-relaxed text-slate-400">
                    System and task prompts are <strong className="font-semibold text-slate-300">fully editable</strong>.
                    Actions appear only after you make changes.
                  </p>
                </div>
              </div>
              {promptDirty || saveAck ? (
                <div className="flex shrink-0 flex-wrap items-center justify-end gap-2">
                  {promptDirty ? (
                    <span className="inline-flex h-7 items-center rounded-md bg-amber-500/10 px-2.5 font-mono text-[9px] uppercase tracking-wide text-amber-200/90 ring-1 ring-amber-500/35">
                      Unsaved changes
                    </span>
                  ) : null}
                  {saveAck ? (
                    <span className="inline-flex h-7 items-center rounded-md bg-[var(--nexus-success)]/10 px-2.5 font-mono text-[9px] uppercase tracking-wide text-[var(--nexus-success)] ring-1 ring-[var(--nexus-success)]/35">
                      Saved
                    </span>
                  ) : null}
                  {promptDirty ? (
                    <>
                      <button
                        type="button"
                        onClick={savePromptsMock}
                        className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/10 px-2.5 font-mono text-[9px] uppercase tracking-wide text-[var(--nexus-glow)] transition-colors hover:border-[var(--nexus-glow)]/70"
                      >
                        Save
                      </button>
                      {promptDefaults ? (
                        <button
                          type="button"
                          onClick={resetPromptsFromPayload}
                          className="inline-flex h-7 items-center gap-1.5 rounded-md border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/90 px-2.5 font-mono text-[9px] uppercase tracking-wide text-slate-200 transition-colors hover:border-[var(--nexus-glow)]/45"
                        >
                          <RotateCcw className="h-3 w-3" aria-hidden />
                          Reset
                        </button>
                      ) : null}
                    </>
                  ) : null}
                </div>
              ) : null}
            </div>

            <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">
              System prompt
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              rows={6}
              placeholder="System prompt for this agent…"
              spellCheck={false}
              className="nexus-prompt-input w-full rounded-lg px-3 py-2 font-mono text-[11px] leading-relaxed placeholder:opacity-90"
            />
            <div className="h-3" />
            <label className="mb-1 block text-[10px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">
              Task prompt
            </label>
            <textarea
              value={taskPrompt}
              onChange={(e) => setTaskPrompt(e.target.value)}
              rows={5}
              placeholder="Task / instruction template…"
              spellCheck={false}
              className="nexus-prompt-input w-full rounded-lg px-3 py-2 font-mono text-[11px] leading-relaxed placeholder:opacity-90"
            />
            <div className="nexus-cot-inner-rule mt-4 flex items-center justify-between gap-3 bg-transparent px-0 py-3">
              <div>
                <div className="text-[10px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">Chain-of-thought</div>
                <div className="mt-0.5 font-mono text-[10px] text-[var(--nexus-text)]">
                  {cotEnabled ? "Enabled by policy" : "Disabled by policy"}
                </div>
              </div>
              <span
                className={`inline-flex h-7 items-center rounded-md px-2.5 font-mono text-[9px] uppercase tracking-wide ring-1 ${
                  cotEnabled
                    ? "bg-[var(--nexus-glow)]/10 text-[var(--nexus-glow)] ring-[var(--nexus-glow)]/35"
                    : "bg-[var(--nexus-surface)]/70 text-slate-300 ring-[var(--nexus-border)]"
                }`}
              >
                Read only
              </span>
            </div>
            {!promptDefaults ? (
              <p className="mt-3 pt-3 text-[10px] leading-relaxed text-[var(--nexus-muted)] font-mono">
                No agent_prompts row for this node — add one in mock data or API.
              </p>
            ) : null}
          </section>

          <section className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/20 p-4">
            <div className="mb-2 flex items-center justify-between gap-2 pb-2">
              <span className="font-mono text-[10px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)]">Traces</span>
              <span className="font-mono text-[10px] text-slate-400">{traces.length} run(s)</span>
            </div>
            {loading && <p className="font-mono text-xs text-[var(--nexus-muted)]">Loading…</p>}
            {!loading && traces.length === 0 && (
              <p className="font-mono text-xs text-[var(--nexus-muted)]">No traces for this agent yet.</p>
            )}
            <div className="space-y-3 pt-1">
              {traces.map((t, i) => (
                <AgentTraceCard key={t.trace_id} trace={t} index={i} />
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
