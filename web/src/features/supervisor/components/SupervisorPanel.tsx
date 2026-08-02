"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { researchConsoleHref } from "@/lib/consoleView";
import { supervisorMemoryCache } from "@/features/supervisor/lib/supervisorMemoryCache";
import type { SavedRunListItem } from "@/types/backtest";
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

function runSortTs(item: SavedRunListItem): number {
  if (typeof item.sort_ts === "number" && Number.isFinite(item.sort_ts)) return item.sort_ts;
  return Date.parse(item.end_iso || item.start_iso || "") || 0;
}

function formatRunOption(item: SavedRunListItem): string {
  const ticker = (item.ticker || "").trim() || "—";
  const ret =
    typeof item.total_return_pct === "number" && Number.isFinite(item.total_return_pct)
      ? `${item.total_return_pct >= 0 ? "+" : ""}${item.total_return_pct.toFixed(1)}%`
      : null;
  const shortId = item.run_id.length > 22 ? `${item.run_id.slice(0, 20)}…` : item.run_id;
  return ret ? `${ticker} · ${ret} · ${shortId}` : `${ticker} · ${shortId}`;
}

function MarkdownMessage({ text }: { text: string }) {
  return (
    <div className="nexus-md nexus-md-chat min-w-0">
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeSanitize]}>
        {text}
      </ReactMarkdown>
    </div>
  );
}

function normalizeChatText(text: string): string {
  return (text || "")
    .replace(/\r\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .replace(/\n\n(?=[-*•]|\d+\.\s)/g, "\n")
    .trim();
}

export function SupervisorPanel({
  initialRunId,
  embedded = false,
}: {
  initialRunId?: string | null;
  embedded?: boolean;
}) {
  const router = useRouter();
  const [target, setTarget] = useState<"live" | "backtest">("backtest");
  const [runId, setRunId] = useState(initialRunId?.trim() || "latest");
  const [savedRuns, setSavedRuns] = useState<SavedRunListItem[]>([]);
  const [savedRunsLoading, setSavedRunsLoading] = useState(true);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [idleHint, setIdleHint] = useState<string | null>(null);
  const [snapshot, setSnapshot] = useState<PmSnapshotResponse | null>(null);
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [question, setQuestion] = useState("");
  const [askBusy, setAskBusy] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const scrollRef = useRef<HTMLDivElement>(null);
  const questionRef = useRef<HTMLTextAreaElement>(null);
  const stickToBottomRef = useRef(true);

  const scrollToBottom = (behavior: ScrollBehavior = "auto") => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  };

  const effectiveRunId = useMemo(() => (runId?.trim() ? runId.trim() : ""), [runId]);
  const cacheKey = useMemo(
    () => `${target}:${effectiveRunId || "none"}`,
    [target, effectiveRunId],
  );
  const resolvedRunId = useMemo(() => {
    const rid = snapshot?.snapshot?.run_id;
    return typeof rid === "string" && rid.trim() ? rid.trim() : null;
  }, [snapshot]);

  useEffect(() => {
    const cached = supervisorMemoryCache.get(cacheKey);
    if (!cached) return;
    if (cached.snapshot) setSnapshot(cached.snapshot);
    if (cached.messages?.length) setMessages(cached.messages);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cacheKey]);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const res = await fetch("/api/health", { cache: "no-store" });
        const data = (await res.json().catch(() => ({}))) as { llm_configured?: boolean };
        if (!cancelled) setLlmConfigured(Boolean(data.llm_configured));
      } catch {
        if (!cancelled) setLlmConfigured(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setSavedRunsLoading(true);
    void (async () => {
      try {
        const base = getFlowApiOrigin();
        const res = await fetch(`${base}/backtests`, { cache: "no-store" });
        const data = (await res.json().catch(() => ({}))) as {
          items?: SavedRunListItem[];
          runs?: string[];
        };
        if (cancelled) return;
        let items = Array.isArray(data.items) ? data.items : [];
        if (!items.length && Array.isArray(data.runs)) {
          items = data.runs.map((run_id) => ({ run_id }));
        }
        items = [...items].sort((a, b) => {
          const tb = runSortTs(b);
          const ta = runSortTs(a);
          if (tb !== ta) return tb - ta;
          return String(b.run_id).localeCompare(String(a.run_id));
        });
        setSavedRuns(items);
      } catch {
        if (!cancelled) setSavedRuns([]);
      } finally {
        if (!cancelled) setSavedRunsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectBacktestRun = useCallback(
    (nextId: string) => {
      const id = nextId.trim();
      if (!id) return;
      setTarget("backtest");
      setRunId(id);
      setIdleHint(null);
      setError(null);
      setSnapshot(null);
      router.replace(id === "latest" ? researchConsoleHref(null) : researchConsoleHref(id), {
        scroll: false,
      });
      window.setTimeout(() => questionRef.current?.focus(), 0);
    },
    [router],
  );

  useEffect(() => {
    const id = initialRunId?.trim() || "";
    if (!id) {
      setTarget("backtest");
      setRunId("latest");
      setIdleHint(
        savedRunsLoading
          ? null
          : savedRuns.length
            ? "Using the latest completed backtest. Pick another from the dropdown to switch."
            : "No Saved runs yet — finish a New backtest on the left, then pick it here.",
      );
      setError(null);
      return;
    }
    const looksBacktest = /^bt[-_]/i.test(id) || /^perp[-_]/i.test(id);
    setTarget(looksBacktest ? "backtest" : "live");
    setRunId(id);
    setIdleHint(null);
    setError(null);
    setSnapshot(null); // force refresh for the newly selected run
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRunId]);

  useEffect(() => {
    supervisorMemoryCache.set(cacheKey, { snapshot, messages });
  }, [cacheKey, messages, snapshot]);

  const load = useCallback(async () => {
    if (!effectiveRunId) {
      setLoading(false);
      setIdleHint("Waiting for a run. Start a Research backtest or live paper session first.");
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const base = getFlowApiOrigin();
      const url =
        target === "backtest"
          ? `${base}/pm/backtests/${encodeURIComponent(effectiveRunId)}/snapshot?llm=0`
          : `${base}/pm/runs/${encodeURIComponent(effectiveRunId)}/snapshot?llm=0`;
      const res = await fetch(url, { cache: "no-store" });
      const data = (await res.json().catch(() => ({}))) as PmSnapshotResponse & {
        error?: string;
        detail?: string | { msg?: string };
      };
      if (!res.ok) {
        const raw = data.error || data.detail || `Snapshot failed (${res.status})`;
        const detail = typeof raw === "string" ? raw : JSON.stringify(raw);
        const soft404 =
          res.status === 404 ||
          /run not found/i.test(detail) ||
          /missing summary/i.test(detail) ||
          /unknown backtest/i.test(detail) ||
          /not found/i.test(detail);
        if (soft404) {
          const midOrIncomplete =
            /missing summary|unknown backtest/i.test(detail) ||
            (Boolean(effectiveRunId) && effectiveRunId !== "latest");
          setIdleHint(
            midOrIncomplete
              ? "That backtest is still running or never finished. Wait for it on the left, or pick a completed run."
              : "No completed Research backtest found yet. Run one on the left, then pick it from the dropdown.",
          );
          setError(null);
          setSnapshot(null);
          if (effectiveRunId && effectiveRunId !== "latest") {
            setRunId("latest");
          }
          return;
        }
        setError(detail);
        return;
      }
      setSnapshot(data);
      if (effectiveRunId === "latest") {
        setIdleHint(null);
      }
    } catch (e) {
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
    if (!effectiveRunId) {
      setError("No run selected. Finish a Research backtest on the left, then pick it from the dropdown.");
      return;
    }
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
        let msg = txt || `Ask failed (${res.status})`;
        try {
          const parsed = JSON.parse(txt) as { detail?: unknown };
          if (typeof parsed.detail === "string") msg = parsed.detail;
        } catch {
          // keep raw text
        }
        if (res.status === 404 || /not found/i.test(msg)) {
          msg =
            "Supervisor could not find that run. Pick a completed Saved run from the dropdown (or open one on the left).";
        }
        setError(msg);
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
        const parts = buf.split("\n\n");
        buf = parts.pop() || "";
        for (const ev of parts) {
          const lines = ev.split("\n");
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            // SSE data: keep whitespace after "data:"
            const raw = line.startsWith("data: ") ? line.slice(6) : line.slice(5);
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
            setMessages((m) => {
              const next = m.map((msg) =>
                msg.id === assistantId ? { ...msg, text: (msg.text || "") + data } : msg,
              );
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
    if (!stickToBottomRef.current) return;
    scrollToBottom("auto");
  }, [messages.length]);

  const selectValue = useMemo(() => {
    if (target !== "backtest") return "";
    if (effectiveRunId && effectiveRunId !== "latest") return effectiveRunId;
    if (resolvedRunId && savedRuns.some((r) => r.run_id === resolvedRunId)) return resolvedRunId;
    if (effectiveRunId === "latest") return "latest";
    return "";
  }, [effectiveRunId, resolvedRunId, savedRuns, target]);

  const runLabel = effectiveRunId
    ? effectiveRunId === "latest"
      ? `latest${resolvedRunId ? ` → ${resolvedRunId}` : ""}`
      : effectiveRunId
    : "—";

  return (
    <div
      id="nexus-supervisor"
      className={
        embedded
          ? "flex h-full min-h-0 w-full flex-col overflow-hidden"
          : "mx-auto flex w-full max-w-6xl flex-col gap-3 px-4 pb-6 pt-10"
      }
    >
      {/* Compact toolbar — keep Research chat tall */}
      <div
        className={
          embedded
            ? "shrink-0 border-b border-[color:var(--nexus-card-stroke)] px-3 py-2"
            : "shrink-0 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4"
        }
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--nexus-glow)]">
                Supervisor
              </p>
              {!embedded ? (
                <h2 className="text-sm font-semibold text-[var(--nexus-text)]">Chat</h2>
              ) : null}
              {llmConfigured === false ? (
                <span className="font-mono text-[9px] text-[rgba(248,113,113,0.95)]">
                  LLM key missing
                </span>
              ) : null}
            </div>
            <div className="mt-1.5 flex min-w-0 flex-col gap-1">
              <label className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                Saved run
              </label>
              <select
                value={selectValue}
                disabled={savedRunsLoading || target === "live"}
                onChange={(e) => {
                  const v = e.target.value;
                  if (!v) return;
                  selectBacktestRun(v);
                }}
                className="nexus-prompt-input h-8 w-full max-w-md truncate rounded-md px-2 font-mono text-[11px] disabled:opacity-50"
                aria-label="Select saved backtest run"
              >
                <option value="latest">
                  {savedRunsLoading
                    ? "Loading runs…"
                    : resolvedRunId
                      ? `Latest completed → ${resolvedRunId}`
                      : "Latest completed"}
                </option>
                {savedRuns.map((item) => (
                  <option key={item.run_id} value={item.run_id}>
                    {formatRunOption(item)}
                  </option>
                ))}
              </select>
              {target === "live" ? (
                <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                  Advanced live target · {runLabel}
                </p>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-1.5 self-end">
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="h-7 rounded-md border border-[color:var(--nexus-card-stroke)] px-2.5 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/40 hover:text-[var(--nexus-text)]"
            >
              {advancedOpen ? "Hide" : "Advanced"}
            </button>
            <button
              type="button"
              onClick={() => void load()}
              disabled={loading}
              className="h-7 rounded-md border border-[color:var(--nexus-card-stroke)] px-2.5 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/40 hover:text-[var(--nexus-text)] disabled:opacity-40"
            >
              {loading ? "…" : "Refresh"}
            </button>
          </div>
        </div>

        {advancedOpen ? (
          <div className="mt-2 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/30 p-2.5">
            <p className="mb-1.5 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
              Manual override
            </p>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-md border border-[color:var(--nexus-card-stroke)] p-0.5">
                <button
                  type="button"
                  onClick={() => setTarget("live")}
                  className={`rounded px-2 py-1 font-mono text-[9px] uppercase ${
                    target === "live"
                      ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                      : "text-[var(--nexus-muted)]"
                  }`}
                >
                  Live
                </button>
                <button
                  type="button"
                  onClick={() => setTarget("backtest")}
                  className={`rounded px-2 py-1 font-mono text-[9px] uppercase ${
                    target === "backtest"
                      ? "bg-[var(--nexus-glow)]/15 text-[var(--nexus-glow)]"
                      : "text-[var(--nexus-muted)]"
                  }`}
                >
                  Backtest
                </button>
              </div>
              <input
                value={runId}
                onChange={(e) => setRunId(e.target.value)}
                onBlur={() => {
                  const id = runId.trim();
                  if (!id) return;
                  if (target === "backtest") selectBacktestRun(id);
                }}
                onKeyDown={(e) => {
                  if (e.key !== "Enter") return;
                  e.preventDefault();
                  const id = runId.trim();
                  if (!id) return;
                  if (target === "backtest") selectBacktestRun(id);
                  else void load();
                }}
                className="nexus-prompt-input h-7 min-w-[10rem] flex-1 rounded-md px-2 font-mono text-[11px]"
                placeholder="paste run id only if needed"
                aria-label="Manual run id"
              />
              <button
                type="button"
                onClick={() => selectBacktestRun("latest")}
                className="h-7 rounded-md border border-[color:var(--nexus-card-stroke)] px-2 font-mono text-[9px] uppercase text-[var(--nexus-muted)]"
              >
                Latest
              </button>
            </div>
          </div>
        ) : null}
        {idleHint ? (
          <p className="mt-1.5 font-mono text-[10px] leading-snug text-[var(--nexus-muted)]">{idleHint}</p>
        ) : null}
        {error ? (
          <p className="mt-1.5 font-mono text-[10px] text-[rgba(248,113,113,0.95)]" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <div
        className={
          embedded
            ? "flex min-h-0 flex-1 flex-col overflow-hidden"
            : "grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,22rem)]"
        }
      >
        <section
          className={
            embedded
              ? "flex min-h-0 flex-1 flex-col overflow-hidden"
              : "flex h-[min(calc(100vh-280px),720px)] min-h-[420px] flex-col overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60"
          }
        >
          <div
            ref={scrollRef}
            className="nexus-scroll min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 py-3"
          >
            {messages.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[color:var(--nexus-card-stroke)] bg-black/20 px-3 py-4 font-mono text-[11px] leading-relaxed text-[var(--nexus-muted)]">
                <p className="text-[var(--nexus-text)]">Ask about this run</p>
                <ul className="mt-2 space-y-1 pl-3">
                  <li className="list-disc">Why did this run trade so much?</li>
                  <li className="list-disc">Did Risk Guard veto anything?</li>
                  <li className="list-disc">What should I tune next?</li>
                </ul>
              </div>
            ) : (
              <div className="flex flex-col gap-2.5">
                {messages.map((m) => {
                  const isUser = m.role === "user";
                  return (
                    <div
                      key={m.id}
                      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={`min-w-0 max-w-[min(100%,28rem)] px-3 py-2 text-[12px] leading-snug ${
                          isUser
                            ? "rounded-2xl rounded-br-md bg-[rgba(0,212,170,0.16)] text-[var(--nexus-text)] ring-1 ring-[rgba(0,212,170,0.4)]"
                            : "rounded-2xl rounded-bl-md border-l-2 border-[rgba(96,165,250,0.65)] bg-[rgba(15,23,42,0.85)] text-[var(--nexus-text)] ring-1 ring-[rgba(96,165,250,0.22)]"
                        }`}
                      >
                        <div className="mb-1 flex items-center justify-between gap-2">
                          <span
                            className={`font-mono text-[9px] uppercase tracking-wider ${
                              isUser ? "text-[var(--nexus-glow)]" : "text-[rgba(147,197,253,0.95)]"
                            }`}
                          >
                            {isUser ? "You" : "Supervisor"}
                          </span>
                          <span className="font-mono text-[9px] tabular-nums text-[var(--nexus-muted)]">
                            {new Date(m.ts).toLocaleTimeString(undefined, {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </span>
                        </div>
                        {m.text ? (
                          isUser ? (
                            <p className="break-words font-sans text-[12px] leading-snug">
                              {m.text}
                            </p>
                          ) : (
                            <MarkdownMessage text={normalizeChatText(m.text)} />
                          )
                        ) : askBusy && !isUser ? (
                          <span className="font-mono text-[11px] text-[var(--nexus-muted)]">
                            Typing…
                          </span>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="shrink-0 border-t border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/90 px-3 py-2.5">
            <div className="flex items-end gap-2">
              <textarea
                id="nexus-supervisor-input"
                ref={questionRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={2}
                placeholder="Message Supervisor…"
                className="nexus-prompt-input max-h-28 min-h-[40px] flex-1 resize-none rounded-xl px-3 py-2 font-sans text-[13px] placeholder:text-[var(--nexus-muted)] focus:border-[var(--nexus-glow)]/40"
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
                disabled={askBusy || !question.trim() || !effectiveRunId}
                title={!effectiveRunId ? "Select a run first" : undefined}
                className="h-10 shrink-0 rounded-xl bg-[var(--nexus-glow)] px-4 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--nexus-bg)] disabled:opacity-40"
              >
                Send
              </button>
            </div>
          </div>
        </section>

        {/* Full-page supervisor only: keep summary aside. Embedded Research = chat-only. */}
        {!embedded ? (
        <aside
          className="flex h-[min(calc(100vh-280px),720px)] min-h-[420px] flex-col overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60 p-4"
        >
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
              Executive summary
            </p>
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
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Brief
                  </p>
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
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Detail
                  </p>
                  <p className="mt-2 whitespace-pre-wrap font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">
                    {snapshot.llm_summary.detail?.trim() ? snapshot.llm_summary.detail.trim() : "—"}
                  </p>
                </div>

                <div className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-black/15 p-3">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Risks
                  </p>
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
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Next actions
                  </p>
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
                  {llmConfigured === false
                    ? "No executive summary yet. Set OPENAI_API_KEY in the repo .env, then restart docker compose."
                    : "No executive summary yet. Hit Generate summary (uses the backend LLM key)."}
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
        ) : null}
      </div>
    </div>
  );
}
