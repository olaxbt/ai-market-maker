"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Save, X } from "lucide-react";

export type PromptEditorValue = {
  system: string;
  task: string;
};

export interface PromptEditorProps {
  agentId: string;
  initialValue: PromptEditorValue;
  readOnly?: boolean;
  subtitle?: string | null;
  onSave: (agentId: string, value: PromptEditorValue) => Promise<void> | void;
  onClose: () => void;
}

function clamp(s: string, n: number): string {
  const t = String(s ?? "");
  if (t.length <= n) return t;
  return `${t.slice(0, n)}…`;
}

export default function PromptEditor({
  agentId,
  initialValue,
  readOnly = false,
  subtitle = null,
  onSave,
  onClose,
}: PromptEditorProps) {
  const [tab, setTab] = useState<"system" | "task">("system");
  const [value, setValue] = useState<PromptEditorValue>(initialValue);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const prevAgentIdRef = useRef<string>(agentId);

  useEffect(() => {
    const prevAgentId = prevAgentIdRef.current;
    const agentChanged = prevAgentId !== agentId;
    prevAgentIdRef.current = agentId;

    setValue((cur) => {
      // If agent changed, always rehydrate from latest initialValue.
      if (agentChanged) return initialValue;

      // If user has edits, don't clobber them on stream refresh.
      const isDirty = cur.system !== initialValue.system || cur.task !== initialValue.task;
      return isDirty ? cur : initialValue;
    });

    // Only reset UI state when switching agents; do NOT flip tabs on stream refresh.
    if (agentChanged) {
      setTab("system");
      setErr(null);
      setSaving(false);
    }
  }, [agentId, initialValue]);

  const dirty = useMemo(
    () => value.system !== initialValue.system || value.task !== initialValue.task,
    [value, initialValue],
  );

  const title = useMemo(() => `Edit prompts — ${agentId}`, [agentId]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4"
      role="dialog"
      aria-modal="true"
      aria-label={title}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-4xl overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/95 shadow-[0_30px_90px_rgba(0,0,0,0.55)] backdrop-blur">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-surface)]/35 px-5 py-4">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Prompt editor
            </p>
            <h2 className="mt-1 break-words font-mono text-sm font-semibold text-[var(--nexus-glow)] nexus-glow-text">
              {agentId}
            </h2>
            <p className="mt-1 text-[11px] leading-relaxed text-[var(--nexus-muted)]">
              {subtitle ??
                (readOnly
                  ? "This node is read-only right now."
                  : "Enterprise-grade editor with safe save + restart semantics.")}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/70 text-slate-200 transition hover:border-[var(--nexus-glow)]/45"
            aria-label="Close"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        <div className="px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <div className="nexus-segmented-toggle flex items-center gap-1 rounded-xl p-1">
                {(
                  [
                    ["system", "System prompt"],
                    ["task", "Task prompt"],
                  ] as const
                ).map(([id, label]) => {
                  const active = tab === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      onClick={() => setTab(id)}
                      className={`nexus-segment-btn rounded-lg px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-all ${
                        active ? "is-active" : ""
                      }`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
              {dirty ? (
                <span className="inline-flex h-8 items-center rounded-lg bg-amber-500/10 px-2.5 font-mono text-[10px] uppercase tracking-widest text-amber-200/90 ring-1 ring-amber-500/35">
                  Unsaved
                </span>
              ) : (
                <span className="inline-flex h-8 items-center rounded-lg bg-[var(--nexus-surface)]/55 px-2.5 font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-muted)] ring-1 ring-[var(--nexus-border)]">
                  {clamp(tab === "system" ? value.system : value.task, 46) || "Empty"}
                </span>
              )}
            </div>

            <div className="flex flex-wrap items-center justify-end gap-2">
              <button
                type="button"
                onClick={onClose}
                className="h-9 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-muted)] transition hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={readOnly || saving || !dirty}
                onClick={async () => {
                  setSaving(true);
                  setErr(null);
                  try {
                    await onSave(agentId, value);
                    onClose();
                  } catch (e) {
                    setErr(e instanceof Error ? e.message : String(e));
                    setSaving(false);
                  }
                }}
                className="inline-flex h-9 items-center gap-2 rounded-lg border border-[var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/10 px-3 font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-glow)] transition hover:border-[var(--nexus-glow)]/70 hover:bg-[var(--nexus-glow)]/15 disabled:opacity-40"
              >
                <Save className="h-4 w-4" aria-hidden />
                {saving ? "Saving…" : "Save & restart"}
              </button>
            </div>
          </div>

          {err ? (
            <div className="mt-3 rounded-lg border border-[rgba(242,92,84,0.35)] bg-[rgba(242,92,84,0.08)] px-3 py-2 font-mono text-[11px] text-[rgba(242,92,84,0.95)]">
              {err}
            </div>
          ) : null}

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="min-w-0">
              <textarea
                value={tab === "system" ? value.system : value.task}
                onChange={(e) =>
                  setValue((v) =>
                    tab === "system"
                      ? { ...v, system: e.target.value }
                      : { ...v, task: e.target.value },
                  )
                }
                spellCheck={false}
                disabled={readOnly || saving}
                className="nexus-prompt-input h-[min(62vh,560px)] w-full resize-none rounded-xl p-4 font-mono text-[12px] leading-relaxed placeholder:opacity-90"
                placeholder={tab === "system" ? "System prompt…" : "Task prompt…"}
              />
            </div>

            <aside className="min-w-0 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/25 p-4">
              <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                Guidelines
              </p>
              <ul className="mt-3 space-y-2 font-mono text-[11px] leading-relaxed text-slate-300">
                <li>
                  <span className="text-[var(--nexus-muted)]">Keep it</span> explicit: constraints,
                  style, and output shape.
                </li>
                <li>
                  <span className="text-[var(--nexus-muted)]">Prefer</span> short sections & bullet
                  lists over walls of text.
                </li>
                <li>
                  <span className="text-[var(--nexus-muted)]">Avoid</span> secrets. Prompts are
                  stored server-side.
                </li>
              </ul>

              <div className="mt-4 border-t border-[var(--nexus-rule-soft)] pt-4">
                <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                  Runtime
                </p>
                <p className="mt-2 font-mono text-[11px] leading-relaxed text-[var(--nexus-muted)]">
                  Save triggers a prompt update via the API and expects the agent runtime to
                  hot-reload.
                </p>
              </div>
            </aside>
          </div>
        </div>
      </div>
    </div>
  );
}
