"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { supervisorMemoryCache } from "@/features/supervisor/lib/supervisorMemoryCache";
import type { PortfolioManagerSnapshotResponse as PmSnapshotResponse } from "@/types/portfolio-manager";

type ChatMsg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  ts: number;
};

function _id(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function MarkdownMessage({ text }: { text: string }) {
  // Render safe markdown (no raw HTML), styled for Nexus.
  return (
    <div className="nexus-md min-w-0">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

function normalizeChatText(text: string): string {
  // Models sometimes emit excessive blank lines during streaming; keep it readable.
  return (text || "").replace(/\n{3,}/g, "\n\n");
}

export function SupervisorPanel({
  initialRunId,
  embedded = false,
}: {
  initialRunId?: string | null;
  embedded?: boolean;
}) {
  const [target, setTarget] = useState<"live" | "backtest">("live");
  const [runId, setRunId] = useState(initialRunId?.trim() || "latest");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<PmSnapshotResponse | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [question, setQuestion] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const stickToBottomRef = useRef(true);

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  };

  const effectiveRunId = useMemo(() => (runId?.trim() ? runId.trim() : "latest"), [runId]);
  const cacheKey = useMemo(() => `${target}:${effectiveRunId}`, [target, effectiveRunId]);
  const resolvedRunId = useMemo(() => {
    const rid = snapshot?.snapshot?.run_id;
    return typeof rid === "string" && rid.trim() ? rid.trim() : null;
  }, [snapshot]);

  // Restore in-RAM state when navigating away/back.
  useEffect(() => {
    const cached = supervisorMemoryCache.get(cacheKey);
    if (!cached) return;
    if (cached.snapshot) setSnapshot(cached.snapshot);
    if (cached.messages?.length) setMessages(cached.messages);
    // Don't restore transient flags (loading/busy/error); those should reflect current view.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  useEffect(() => {
    const id = initialRunId?.trim() || "";
    if (!id) return;
    // If a backtest run id is provided via URL (Research / Backtest lab), bind Supervisor to it.
    const looksBacktest = /^bt[-_]/i.test(id);
    if (looksBacktest) setTarget("backtest");
    setRunId(id);
    // When switching runs via URL, clear ephemeral error; keep messages cached per cacheKey.
    setError(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRunId]);

  // Keep cache hot without re-fetching.
  useEffect(() => {
    supervisorMemoryCache.set(cacheKey, { snapshot, messages });
  }, [cacheKey, messages, snapshot]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const base = getFlowApiOrigin();
      // Default refresh is snapshot-only (no LLM) to avoid burning tokens on navigation/state changes.
      const url =
        target === "backtest"
          ? `${base}/pm/backtests/${encodeURIComponent(effectiveRunId)}/snapshot?llm=0`
          : `${base}/pm/runs/${encodeURIComponent(effectiveRunId)}/snapshot?llm=0`;
      const res = await fetch(url, { cache: "no-store" });
      const data = (await res.json().catch(() => ({}))) as PmSnapshotResponse & {
        error?: string;
        detail?: string;
      };
      if (!res.ok) {
        // Keep any cached snapshot in view; only surface the error.
        setError(data.error || data.detail || `Snapshot failed (${res.status})`);
        return;
      }
      setSnapshot(data);
    } catch (e) {
      // Keep any cached snapshot in view; only surface the error.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [effectiveRunId, target]);

  const generateSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const base = getFlowApiOrigin();
      const url =
        target === "backtest"
          ? `${base}/pm/backtests/${encodeURIComponent(effectiveRunId)}/snapshot?llm=1`
          : `${base}/pm/runs/${encodeURIComponent(effectiveRunId)}/snapshot?llm=1`;
      const res = await fetch(url, { cache: "no-store" });
      const data = (await res.json().catch(() => ({}))) as PmSnapshotResponse & {
        error?: string;
        detail?: string;
      };
      if (!res.ok) {
        setError(data.error || data.detail || `Summary failed (${res.status})`);
        return;
      }
      setSnapshot(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [effectiveRunId, target]);

  const ask = useCallback(async () => {
    const q = question.trim();
    if (!q) return;
    setAskBusy(true);
    setError(null);
    const userMsg: ChatMsg = { id: _id("u"), role: "user", text: q, ts: Date.now() };
    setMessages((m) => {
      const next = [...m, userMsg];
      supervisorMemoryCache.set(cacheKey, { snapshot, messages: next });
      return next;
    });
    setQuestion("");
    try {
      const base = getFlowApiOrigin();
      const streamUrl =
        target === "backtest"
          ? `${base}/pm/backtests/${encodeURIComponent(effectiveRunId)}/ask_stream`
          : `${base}/pm/runs/${encodeURIComponent(effectiveRunId)}/ask_stream`;

      const assistantId = _id("a");
      const startTs = Date.now();
      setMessages((m) => {
        const placeholder: ChatMsg = { id: assistantId, role: "assistant", text: "", ts: startTs };
        const next = [...m, placeholder];
        supervisorMemoryCache.set(cacheKey, { snapshot, messages: next });
        return next;
      });

      const res = await fetch(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify({ question: q, max_tokens: 650 }),
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        setError(txt || `Ask failed (${res.status})`);
        return;
      }
      if (!res.body) {
        setError("Streaming response missing body");
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      let done = false;
      while (!done) {
        const { value, done: rdDone } = await reader.read();
        done = rdDone;
        if (!value) continue;
        buf += decoder.decode(value, { stream: true });
        // Parse SSE events separated by blank lines.
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const ev of parts) {
          const lines = ev.split("\n");
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            // Per SSE spec, "data:" may be followed by a single optional space.
            // Do NOT trim arbitrary leading whitespace; it breaks token streaming (spaces/newlines).
            const raw = line.startsWith("data: ") ? line.slice(6) : line.slice(5);
            // If backend emitted an empty data line, that represents a newline in the original text.
            const data = raw.length === 0 ? "\n" : raw;
            if (data === "[DONE]") {
              done = true;
              break;
            }
            if (data.startsWith("[ERROR]")) {
              setError(data);
              done = true;
              break;
            }
            // Append chunk to assistant message.
            setMessages((m) => {
              const next = m.map((msg) => (msg.id === assistantId ? { ...msg, text: (msg.text || "") + data } : msg));
              supervisorMemoryCache.set(cacheKey, { snapshot, messages: next });
              return next;
            });
            if (stickToBottomRef.current) {
              window.setTimeout(() => scrollToBottom("auto"), 0);
            }
          }
          if (done) break;
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setAskBusy(false);
    }
  }, [cacheKey, effectiveRunId, question, snapshot, target]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;

    const NEAR_BOTTOM_PX = 120;
    const onScroll = () => {
      const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
      stickToBottomRef.current = distance <= NEAR_BOTTOM_PX;
    };

    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    // When a new message is added, stick to bottom if user is already there.
    if (!stickToBottomRef.current) return;
    scrollToBottom("auto");
  }, [messages.length]);

  // Shared pane height so Chat and Summary align.
  // In embedded layout (split view), let the parent control height.
  const paneHeightClass = embedded
    ? "min-h-0"
    : "h-[min(calc(100vh-320px),740px)] min-h-[420px]";

  return (
    <div
      className={
        embedded
          ? "min-h-0 w-full px-2 pb-2 pt-2"
          : "mx-auto w-full max-w-6xl space-y-4 px-4 pb-6 pt-10"
      }
    >
      <div className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-glow)]">Supervisor</p>
            <h2 className="mt-1 text-base font-semibold">Supervisor (live system + backtests)</h2>
            <p className="mt-1 text-[12px] leading-relaxed text-[var(--nexus-muted)]">
              Always LLM-enabled. Requires backend <code className="font-mono text-[var(--nexus-text)]">OPENAI_API_KEY</code>.
            </p>
            <p className="mt-2 font-mono text-[11px] text-[var(--nexus-muted)]">
              Target:{" "}
              <span className="text-[var(--nexus-text)]">
                {target === "live" ? "live" : "backtest"} ·{" "}
                {effectiveRunId === "latest" ? `latest${resolvedRunId ? ` → ${resolvedRunId}` : ""}` : effectiveRunId}
              </span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="h-8 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] outline-none hover:border-[var(--nexus-glow)]/40"
            >
              {advancedOpen ? "Hide" : "Advanced"}
            </button>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="h-8 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/70 px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] outline-none hover:border-[var(--nexus-glow)]/40 disabled:opacity-40"
            >
              {loading ? "Loading…" : "Refresh"}
            </button>
          </div>
        </div>

        {advancedOpen ? (
          <div className="mt-3 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/30 p-3">
            <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
              Target & manual run id (optional)
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <div className="mr-2 inline-flex rounded-lg border border-[color:var(--nexus-card-stroke)] p-1">
                <button
                  type="button"
                  onClick={() => setTarget("live")}
                  className={`rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wide ${
                    target === "live"
                      ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                      : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
                  }`}
                >
                  Live
                </button>
                <button
                  type="button"
                  onClick={() => setTarget("backtest")}
                  className={`rounded px-2 py-1 font-mono text-[9px] uppercase tracking-wide ${
                    target === "backtest"
                      ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                      : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
                  }`}
                >
                  Backtest
                </button>
              </div>
              <input
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                className="nexus-prompt-input h-8 w-[min(26rem,92vw)] rounded-lg px-2 font-mono text-[11px] focus:border-[var(--nexus-glow)]/40"
                placeholder="latest (default) or explicit run id"
                aria-label="Backtest run id override"
              />
              <button
                type="button"
                onClick={() => setRunId("latest")}
                className="h-8 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/40 px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/40"
              >
                Use latest
              </button>
            </div>
          </div>
        ) : null}
        {error ? (
          <div className="mt-3 rounded border border-red-900/45 bg-red-950/35 px-3 py-2 font-mono text-[11px] text-red-100">{error}</div>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,460px)]">
        <section
          className={`flex min-h-0 flex-col rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60 p-4 ${paneHeightClass}`}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Chat</p>
            <span className="font-mono text-[10px] text-[var(--nexus-muted)]">run={effectiveRunId}</span>
          </div>

          <div
            ref={scrollRef}
            className="nexus-scroll mt-3 min-h-0 flex-1 overflow-auto overflow-x-hidden rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3"
          >
            {messages.length === 0 ? (
              <div className="font-mono text-[11px] leading-relaxed text-[var(--nexus-muted)]">
                Ask a question to start. Examples:
                <ul className="mt-2 list-disc pl-5">
                  <li>Why did this run trade so much?</li>
                  <li>Did Risk Guard veto anything? Why?</li>
                  <li>What should I tune next to reduce churn?</li>
                </ul>
              </div>
            ) : (
              <div className="space-y-3.5">
                {messages.map((m) => (
                  <div key={m.id} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"} mb-2`}>
                    <div
                      className={`min-w-0 max-w-[min(34rem,92%)] rounded-2xl px-4 py-3 font-mono text-[12px] leading-relaxed shadow-sm ${
                        m.role === "user"
                          ? "bg-gradient-to-b from-[rgba(0,212,170,0.20)] via-[rgba(0,212,170,0.10)] to-[rgba(59,130,246,0.05)] text-[var(--nexus-text)] ring-1 ring-[rgba(0,212,170,0.38)] shadow-[0_0_18px_rgba(0,212,170,0.06)]"
                          : "bg-[var(--nexus-surface)]/70 text-[var(--nexus-text)] ring-1 ring-[rgba(138,149,166,0.20)] shadow-[0_0_16px_rgba(0,0,0,0.20)]"
                      }`}
                    >
                      <div className="mb-1 flex items-center justify-between gap-3">
                        <span
                          className={`text-[10px] uppercase tracking-wider ${
                            m.role === "user" ? "text-[var(--nexus-glow)]" : "text-[var(--nexus-muted)]"
                          }`}
                        >
                          {m.role === "user" ? "You" : "Supervisor"}
                        </span>
                        <span className="text-[10px] tabular-nums text-[var(--nexus-muted)]">
                          {new Date(m.ts).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <div
                        className={`whitespace-pre-wrap break-words ${m.role === "assistant" ? "pl-0.5" : ""}`}
                      >
                        {m.text ? (
                          <MarkdownMessage text={normalizeChatText(m.text)} />
                        ) : askBusy && m.role === "assistant" ? (
                          <span className="text-[var(--nexus-muted)]">Typing…</span>
                        ) : (
                          ""
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-3 flex items-end gap-2">
            <textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              rows={2}
              placeholder="Message Supervisor…"
              className="nexus-prompt-input min-h-[44px] flex-1 resize-none rounded-xl p-3 font-mono text-[12px] placeholder:text-[var(--nexus-muted)] focus:border-[var(--nexus-glow)]/40"
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void ask();
                }
              }}
            />
            <button
              type="button"
              onClick={() => void ask()}
              disabled={askBusy || !question.trim()}
              className="h-[44px] rounded-xl bg-[var(--nexus-glow)]/12 px-4 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] outline-none ring-1 ring-[var(--nexus-glow)]/25 hover:bg-[var(--nexus-glow)]/16 disabled:opacity-40"
            >
              Send
            </button>
          </div>
        </section>

        <aside
          className={`flex min-h-0 flex-col rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60 p-4 ${paneHeightClass}`}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Executive summary</p>
            <button
              type="button"
              onClick={() => setShowRaw((v) => !v)}
              className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/50 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
            >
              {showRaw ? "Hide raw" : "Show raw"}
            </button>
          </div>

          <div className="nexus-scroll mt-3 min-h-0 flex-1 overflow-auto overflow-x-hidden">
            {snapshot?.llm_summary ? (
              <div className="space-y-3">
                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Brief</p>
                  <ul className="mt-2 space-y-1.5 font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">
                    {(snapshot.llm_summary.brief ?? []).length ? (
                      (snapshot.llm_summary.brief ?? []).slice(0, 8).map((b, idx) => (
                        <li key={idx} className="flex gap-2">
                          <span className="text-[var(--nexus-glow)]">•</span>
                          <span className="min-w-0">{b}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-[var(--nexus-muted)]">—</li>
                    )}
                  </ul>
                </div>

                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Detail</p>
                  <p className="mt-2 whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">
                    {snapshot.llm_summary.detail?.trim() ? snapshot.llm_summary.detail.trim() : "—"}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Risks</p>
                  <ul className="mt-2 space-y-1.5 font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">
                    {(snapshot.llm_summary.risks ?? []).length ? (
                      (snapshot.llm_summary.risks ?? []).slice(0, 8).map((r, idx) => (
                        <li key={idx} className="flex gap-2">
                          <span className="text-[var(--nexus-danger)]">•</span>
                          <span className="min-w-0">{r}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-[var(--nexus-muted)]">—</li>
                    )}
                  </ul>
                </div>

                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">Next actions</p>
                  <ul className="mt-2 space-y-1.5 font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">
                    {(snapshot.llm_summary.next_actions ?? []).length ? (
                      (snapshot.llm_summary.next_actions ?? []).slice(0, 10).map((a, idx) => (
                        <li key={idx} className="flex gap-2">
                          <span className="text-[var(--nexus-glow)]">•</span>
                          <span className="min-w-0">{a}</span>
                        </li>
                      ))
                    ) : (
                      <li className="text-[var(--nexus-muted)]">—</li>
                    )}
                  </ul>
                </div>

                {showRaw ? (
                  <pre className="nexus-scroll max-h-[320px] overflow-auto overflow-x-hidden whitespace-pre-wrap break-words rounded-xl bg-black/20 p-3 font-mono text-[11px] leading-relaxed text-[var(--nexus-text)]">
                    {snapshot ? JSON.stringify(snapshot.snapshot, null, 2) : "—"}
                  </pre>
                ) : null}
              </div>
            ) : (
              <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                <p className="font-mono text-[11px] leading-relaxed text-[var(--nexus-muted)]">
                  No executive summary yet. Ensure backend has{" "}
                  <code className="font-mono text-[var(--nexus-text)]">OPENAI_API_KEY</code> set, then hit Generate summary.
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => void generateSummary()}
                    disabled={loading}
                    className="h-8 rounded-lg border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] outline-none hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
                  >
                    {loading ? "Generating…" : "Generate summary"}
                  </button>
                </div>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

