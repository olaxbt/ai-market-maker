"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { BarChart3, Network, MessageSquareText, ChevronDown } from "lucide-react";

type Step =
  | { action: "message"; text: string }
  | { action: "navigate"; path: string }
  | { action: "tool_call"; tool: string; text: string }
  | { action: "tool_result"; tool: string; text: string }
  | { action: "update_config"; config: Record<string, any> }
  | { action: "run_backtest" }
  | { action: "reset" };

const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

type ChatMsg = { role: "system" | "user" | "assistant"; text: string };

type StudioSession = {
  id: string;
  title: string;
  created_at_ms: number;
  messages: ChatMsg[];
};

const STUDIO_SESSIONS_KEY = "aimm.studio.sessions.v1";
const STUDIO_ACTIVE_SESSION_KEY = "aimm.studio.active_session_id.v1";

function nowMs() {
  return Date.now();
}

function newId() {
  return `st_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

function defaultSession(): StudioSession {
  return {
    id: newId(),
    title: "New chat",
    created_at_ms: nowMs(),
    messages: [
      {
        role: "system",
        text:
          "Studio is the guided entry point.\n\nUse it to understand the system, learn how to reproduce results locally, and publish to the leaderboard.\n\nTry: `onboarding`, `publish to leaderboard`, or describe your strategy idea.",
      },
    ],
  };
}

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

export default function StudioPage() {
  const [sessions, setSessions] = useState<StudioSession[]>([defaultSession()]);
  const [activeId, setActiveId] = useState<string>(sessions[0]?.id ?? "");
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasHydrated = useRef(false);

  const active = useMemo(() => sessions.find((s) => s.id === activeId) ?? sessions[0], [sessions, activeId]);
  const messages = active?.messages ?? [];
  const canSend = useMemo(() => input.trim().length > 0 && !busy, [input, busy]);

  useEffect(() => {
    if (hasHydrated.current) return;
    hasHydrated.current = true;
    try {
      const saved = safeJsonParse<StudioSession[]>(localStorage.getItem(STUDIO_SESSIONS_KEY));
      const savedActive = localStorage.getItem(STUDIO_ACTIVE_SESSION_KEY);
      if (Array.isArray(saved) && saved.length > 0) {
        setSessions(saved);
        setActiveId(savedActive && saved.some((s) => s.id === savedActive) ? savedActive : saved[0].id);
        return;
      }
      // Ensure keys exist for a clean first-run experience.
      const first = defaultSession();
      setSessions([first]);
      setActiveId(first.id);
      localStorage.setItem(STUDIO_SESSIONS_KEY, JSON.stringify([first]));
      localStorage.setItem(STUDIO_ACTIVE_SESSION_KEY, first.id);
    } catch {
      // Ignore storage failures (private browsing etc).
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STUDIO_SESSIONS_KEY, JSON.stringify(sessions));
      localStorage.setItem(STUDIO_ACTIVE_SESSION_KEY, activeId);
    } catch {
      // ignore
    }
  }, [sessions, activeId]);

  function selectSession(id: string) {
    setError(null);
    setActiveId(id);
  }

  function createSession() {
    setError(null);
    const s = defaultSession();
    setSessions((prev) => [s, ...prev]);
    setActiveId(s.id);
    setInput("");
  }

  function renameSessionIfNeeded(sessionId: string, userText: string) {
    const t = userText.trim().replace(/\s+/g, " ");
    if (!t) return;
    setSessions((prev) =>
      prev.map((s) => {
        if (s.id !== sessionId) return s;
        if (s.title !== "New chat") return s;
        return { ...s, title: t.slice(0, 44) };
      }),
    );
  }

  async function send(overrideText?: string) {
    const text = (overrideText ?? input).trim();
    if (!text || busy) return;
    setInput("");
    setError(null);
    setBusy(true);
    const sessionId = active?.id ?? activeId;
    const baseMsgs = (sessions.find((s) => s.id === sessionId)?.messages ?? active?.messages ?? []).slice(0);
    const nextMsgs = [...baseMsgs, { role: "user" as const, text }];
    renameSessionIfNeeded(sessionId, text);
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? { ...s, messages: [...s.messages, { role: "user", text }] } : s)),
    );
    try {
      const res = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation: nextMsgs.slice(-8) }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || data?.detail || `HTTP ${res.status}`);
      }
      const steps: Step[] = Array.isArray(data?.steps) ? data.steps : [];
      for (const s of steps) {
        if (s.action === "navigate" && s.path) {
          window.location.href = s.path;
          break;
        }
        if (s.action === "message" && s.text) {
          setSessions((prev) =>
            prev.map((ss) =>
              ss.id === sessionId ? { ...ss, messages: [...ss.messages, { role: "assistant", text: s.text }] } : ss,
            ),
          );
        }
      }
    } catch (e: any) {
      setError(e?.message || "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="h-full min-h-0">
      <div className="grid h-full min-h-0 w-full grid-cols-1 gap-0 px-0 py-0 md:grid-cols-[260px_1fr]">
        {/* Left rail */}
        <aside className="min-h-0 border-r border-[rgba(15,23,42,0.08)] bg-[rgba(255,255,255,0.55)] p-4 backdrop-blur">
          {/* App tabs */}
          <div className="mb-4 space-y-1">
            <RailTab href="/leaderboard" label="Leaderboard" icon={<BarChart3 className="h-4 w-4" />} />
            <RailTab href="/console" label="Nexus" icon={<Network className="h-4 w-4" />} />
            <RailTab
              href="/studio"
              label="Studio"
              icon={<MessageSquareText className="h-4 w-4" />}
              active
            />
          </div>

          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="studio-kicker">Sessions</div>
              <div className="mt-1 text-[12px] font-semibold text-[rgba(15,23,42,0.82)]">Chats</div>
            </div>
            <button
              type="button"
              onClick={createSession}
              className="rounded-2xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold text-[rgba(0,160,130,0.95)] shadow-sm hover:bg-[rgba(0,212,170,0.14)]"
            >
              New chat
            </button>
          </div>

          <div className="mt-3 max-h-[260px] overflow-auto pr-1">
            <div className="space-y-1">
              {sessions.map((s) => {
                const isActive = s.id === activeId;
                return (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => selectSession(s.id)}
                    className={`w-full rounded-2xl border px-3 py-2 text-left text-[11px] transition ${
                      isActive
                        ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] text-[var(--nexus-text)]"
                        : "border-[rgba(15,23,42,0.08)] bg-[rgba(255,255,255,0.55)] text-[rgba(15,23,42,0.82)] hover:bg-[rgba(255,255,255,0.75)]"
                    }`}
                    title={s.title}
                  >
                    <div className="truncate">{s.title}</div>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-4">
            <Collapsible label="Quick actions" defaultOpen>
              <div className="mt-2 grid gap-2">
                <button
                  type="button"
                  onClick={() => void send("onboarding")}
                  disabled={busy}
                  className="w-full rounded-2xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-left text-[11px] font-semibold text-[rgba(0,212,170,0.95)] shadow-sm hover:bg-[rgba(0,212,170,0.12)] disabled:opacity-40"
                >
                  Clone + run locally
                </button>
                <button
                  type="button"
                  onClick={() => void send("publish to leaderboard")}
                  disabled={busy}
                  className="w-full rounded-2xl border border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.55)] px-3 py-2 text-left text-[11px] text-[rgba(15,23,42,0.88)] shadow-sm hover:bg-[rgba(255,255,255,0.75)] disabled:opacity-40"
                >
                  Publish a backtest
                </button>
                <button
                  type="button"
                  onClick={() => void send("openclaw setup")}
                  disabled={busy}
                  className="w-full rounded-2xl border border-[rgba(99,102,241,0.18)] bg-[rgba(99,102,241,0.08)] px-3 py-2 text-left text-[11px] text-[rgba(79,70,229,0.92)] shadow-sm hover:bg-[rgba(99,102,241,0.12)] disabled:opacity-40"
                >
                  OpenClaw setup
                </button>
              </div>
            </Collapsible>
          </div>

          <div className="mt-4">
            <Collapsible label="Links" defaultOpen={false}>
              <div className="mt-2 flex flex-wrap gap-2">
                <Link
                  href="/get-started"
                  className="rounded-2xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] text-[rgba(0,212,170,0.95)] hover:bg-[rgba(0,212,170,0.12)]"
                >
                  Get Started
                </Link>
                <Link
                  href="/control"
                  className="rounded-2xl border border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.55)] px-3 py-2 text-[11px] text-[rgba(15,23,42,0.85)] hover:bg-[rgba(255,255,255,0.75)]"
                >
                  Control
                </Link>
                <Link
                  href="/tools"
                  className="rounded-2xl border border-[rgba(99,102,241,0.18)] bg-[rgba(99,102,241,0.08)] px-3 py-2 text-[11px] text-[rgba(79,70,229,0.92)] hover:bg-[rgba(99,102,241,0.12)]"
                >
                  Tools
                </Link>
                <a
                  href={REPO_URL}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="rounded-2xl border border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.55)] px-3 py-2 text-[11px] text-[rgba(15,23,42,0.72)] hover:bg-[rgba(255,255,255,0.75)]"
                >
                  GitHub
                </a>
              </div>
            </Collapsible>
          </div>
        </aside>

        {/* Chat */}
        <section className="min-h-0 bg-[rgba(255,255,255,0.35)]">
          <div className="flex h-full min-h-0 flex-col">
            <div className="shrink-0 border-b border-[rgba(15,23,42,0.08)] px-10 py-6">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="studio-kicker">Chat</div>
                  <div className="mt-1 text-[14px] text-[rgba(15,23,42,0.70)]">
                    Strategy iteration with receipts + repeatable loops.
                  </div>
                </div>
                <div className="text-[10px] text-[rgba(15,23,42,0.55)]">{busy ? "Thinking…" : "Ready"}</div>
              </div>
            </div>

            <div className="min-h-0 flex-1 overflow-auto px-10 py-8">
              <div className="mx-auto w-full max-w-[900px] space-y-4">
                {messages.map((m, idx) => (
                  <div key={idx} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                    <div
                      className={`max-w-[92%] whitespace-pre-wrap rounded-3xl border px-4 py-3 text-[12px] leading-relaxed ${
                        m.role === "user"
                          ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] text-[rgba(15,23,42,0.92)]"
                          : m.role === "system"
                            ? "border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.65)] text-[rgba(15,23,42,0.75)]"
                            : "border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.72)] text-[rgba(15,23,42,0.88)]"
                      }`}
                    >
                      {m.text}
                    </div>
                  </div>
                ))}
              </div>

              {error && (
                <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.25)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
                  {error}
                </div>
              )}
            </div>

            <div className="shrink-0 px-10 pb-10">
              <div className="mx-auto w-full max-w-[980px] rounded-[26px] border border-[rgba(15,23,42,0.10)] bg-[rgba(255,255,255,0.86)] px-4 py-4 shadow-[0_18px_50px_rgba(2,6,23,0.12)] backdrop-blur">
                <div className="flex items-center gap-3">
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === "Enter" && void send()}
                    placeholder={busy ? "Thinking…" : "Ask: onboarding, publish to leaderboard, or a strategy idea…"}
                    disabled={busy}
                    className="flex-1 rounded-[20px] border border-[rgba(15,23,42,0.10)] bg-white/80 px-5 py-4 text-[13px] text-[rgba(15,23,42,0.92)] outline-none placeholder:text-[rgba(15,23,42,0.45)] focus:border-[rgba(0,212,170,0.30)] disabled:opacity-50"
                  />
                  <button
                    onClick={() => void send()}
                    disabled={!canSend}
                    className="rounded-[20px] bg-[rgba(0,212,170,0.16)] px-5 py-4 text-[12px] font-semibold text-[rgba(0,160,130,0.95)] disabled:opacity-30 hover:bg-[rgba(0,212,170,0.22)]"
                  >
                    Send
                  </button>
                </div>
              </div>
              <div className="mx-auto mt-3 w-full max-w-[980px] text-[11px] text-[rgba(15,23,42,0.55)]">
                Tip: use <b>Get Started</b> to run locally; use <b>Control</b> to run backtests and inspect receipts.
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function RailTab({
  href,
  label,
  icon,
  active,
}: {
  href: string;
  label: string;
  icon: React.ReactNode;
  active?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`flex items-center gap-2 rounded-2xl border px-3 py-2 text-[12px] transition ${
        active
          ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] font-semibold text-[rgba(0,160,130,0.95)]"
          : "border-[rgba(15,23,42,0.08)] bg-[rgba(255,255,255,0.45)] text-[rgba(15,23,42,0.75)] hover:bg-[rgba(255,255,255,0.70)]"
      }`}
    >
      <span className={active ? "text-[rgba(0,160,130,0.95)]" : "text-[rgba(15,23,42,0.55)]"}>{icon}</span>
      <span>{label}</span>
    </Link>
  );
}

function Collapsible({
  label,
  defaultOpen,
  children,
}: {
  label: string;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 text-[10px] uppercase tracking-[0.18em] text-[var(--nexus-muted)]"
      >
        <span>{label}</span>
        <ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open ? <div>{children}</div> : null}
    </div>
  );
}

