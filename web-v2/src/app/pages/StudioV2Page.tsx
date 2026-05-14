import React, { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";
import { EllipsisVertical, Pencil, Plus, Search, Trash2, Zap } from "lucide-react";
import ChatMessage from "../components/ChatMessage";
import ChatInput from "../components/ChatInput";
import { BacktestInlineWidget } from "../components/BacktestInlineWidget";
import { Input } from "../components/ui/input";
import { ScrollArea } from "../components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "../components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../components/ui/alert-dialog";

type Step =
  | { action: "message"; text: string }
  | { action: "navigate"; path: string }
  | { action: "tool_call"; tool: string; text: string }
  | { action: "tool_result"; tool: string; text: string }
  | { action: "update_config"; config: Record<string, any> }
  | { action: "run_backtest" }
  | { action: "reset" };

type ChatMsg = { id: string; role: "system" | "user" | "assistant"; text: string };

type StudioSession = {
  id: string;
  title: string;
  created_at_ms: number;
  messages: ChatMsg[];
};

const STUDIO_SESSIONS_KEY = "aimm.studio.sessions.v2";
const STUDIO_ACTIVE_SESSION_KEY = "aimm.studio.active_session_id.v2";

function nowMs() {
  return Date.now();
}

function defaultSessionTitle(createdAtMs: number) {
  void createdAtMs;
  return "New conversation";
}

function summarizeTitleFromUserText(userText: string): string {
  const raw = (userText || "").trim().replace(/\s+/g, " ");
  if (!raw) return "New conversation";
  const t = raw.toLowerCase();

  // Heuristic "AI-like" titles for common intents without calling the LLM.
  if (t.includes("backtest")) {
    const sym = raw.match(/\b[A-Z]{2,6}\/[A-Z]{2,6}\b/)?.[0] ?? raw.match(/\b[A-Z]{2,6}-[A-Z]{2,6}\b/)?.[0];
    const bars = raw.match(/\b(\d{2,6})\s*(bars?|candles?)\b/i)?.[1];
    const parts = ["Backtest"];
    if (sym) parts.push(sym.replace("-", "/"));
    if (bars) parts.push(`${bars} bars`);
    return parts.join(" · ").slice(0, 52);
  }
  if (t.includes("publish") && t.includes("leaderboard")) return "Publish to leaderboard";
  if (t.includes("onboarding")) return "Onboarding";

  // Strip some filler prefixes.
  const stripped = raw
    .replace(/^(please\s+)?(can you|could you|help me|i want to|i need to)\s+/i, "")
    .replace(/^run\s+/, "");

  // Take first clause/sentence.
  const first = stripped.split(/[.!?\n]/)[0]?.trim() || stripped;
  const words = first.split(" ").filter(Boolean);
  const short = words.slice(0, 7).join(" ");
  return (short || first || raw).slice(0, 52) || "New conversation";
}

function isPlaceholderSessionTitle(title: string): boolean {
  const t = (title || "").trim().toLowerCase();
  if (!t) return true;
  if (t === "new conversation" || t === "new chat" || t === "chat" || t === "untitled") return true;
  return (title || "").trim().startsWith("Chat •");
}

function applyHeuristicTitleIfPlaceholder(session: StudioSession, userText: string): StudioSession {
  if (!isPlaceholderSessionTitle(session.title)) return session;
  const t = summarizeTitleFromUserText(userText);
  if (!t) return session;
  return { ...session, title: t.slice(0, 52) };
}

function newId() {
  return `st_${Math.random().toString(16).slice(2)}_${Date.now().toString(16)}`;
}

function newMsg(role: ChatMsg["role"], text: string): ChatMsg {
  return { id: newId(), role, text };
}

function defaultSession(): StudioSession {
  const created = nowMs();
  return {
    id: newId(),
    title: defaultSessionTitle(created),
    created_at_ms: created,
    messages: [
      newMsg(
        "system",
        "Welcome to Studio.\n\nAsk about the AI Market Maker project, request onboarding steps, or iterate on a strategy idea.\n\nTry: `onboarding`, `publish to leaderboard`, or describe your strategy.",
      ),
    ],
  };
}

function normalizeSessions(rows: StudioSession[]): StudioSession[] {
  return rows.map((s) => ({
    ...s,
    id: s.id || newId(),
    created_at_ms: s.created_at_ms || nowMs(),
    title: s.title || defaultSessionTitle(s.created_at_ms || nowMs()),
    messages: Array.isArray((s as any).messages)
      ? (s as any).messages.map((m: any) => ({
          id: m?.id || newId(),
          role: m?.role === "user" || m?.role === "assistant" || m?.role === "system" ? m.role : "system",
          text: typeof m?.text === "string" ? m.text : "",
        }))
      : [newMsg("system", "Welcome to Studio.")],
  }));
}

function safeJsonParse<T>(raw: string | null): T | null {
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function formatTimestamp(ms: number) {
  try {
    return new Date(ms).toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

function friendlyError(raw: string): string {
  const t = (raw || "").trim();
  if (!t) return "Request failed";
  // FastAPI often returns JSON in `detail`; surface the useful hint.
  const parsed = safeJsonParse<any>(t);
  const detail = parsed?.detail;
  if (detail && typeof detail === "object") {
    const hint = (detail.hint ?? detail.error ?? "").toString().trim();
    if (hint) return hint;
  }
  if (detail && typeof detail === "string") return detail;
  // Sometimes the API returns the dict itself as the message.
  if (parsed && typeof parsed === "object") {
    const hint = (parsed.hint ?? parsed.error ?? "").toString().trim();
    if (hint) return hint;
  }
  return t;
}

function parseBacktestRunIdFromToolResult(text: string): string | null {
  const t = (text || "").trim();
  if (!t) return null;
  try {
    const j = JSON.parse(t);
    const rid = (j?.run_id ?? "").toString().trim();
    return rid || null;
  } catch {
    return null;
  }
}

function isBacktestMarker(text: string): boolean {
  return (text || "").startsWith("__AIMM_BACKTEST__:");
}

function backtestRunIdFromMarker(text: string): string | null {
  const raw = (text || "").slice("__AIMM_BACKTEST__:".length).trim();
  return raw || null;
}

export default function StudioV2Page() {
  const location = useLocation();
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<StudioSession[]>([defaultSession()]);
  const [activeId, setActiveId] = useState<string>(sessions[0]?.id ?? "");
  const [draft, setDraft] = useState<StudioSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasHydrated = useRef(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const pendingAnchorIdRef = useRef<string | null>(null);
  const pendingAnchorNeedsTailRef = useRef(false);
  const anchorLockRef = useRef(false);
  const [bottomPadPx, setBottomPadPx] = useState(0);
  const [sessionFilter, setSessionFilter] = useState("");
  const lastSeededRunRef = useRef<string | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const [renameId, setRenameId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const pinnedToBottomRef = useRef(true);

  const active = useMemo(() => {
    if (draft && activeId === draft.id) return draft;
    return sessions.find((s) => s.id === activeId) ?? sessions[0];
  }, [sessions, activeId, draft]);
  const messages = active?.messages ?? [];

  const filteredSessions = useMemo(() => {
    const q = sessionFilter.trim().toLowerCase();
    if (!q) return sessions;
    return sessions.filter((s) => (s.title || "").toLowerCase().includes(q) || (s.id || "").toLowerCase().includes(q));
  }, [sessions, sessionFilter]);

  const listSessions = useMemo(() => {
    // Do not show draft in the left list until the user sends a message.
    return filteredSessions;
  }, [filteredSessions]);

  function fmtDate(ms: number) {
    try {
      if (!ms) return "";
      return new Date(ms).toLocaleString([], { month: "short", day: "2-digit" });
    } catch {
      return "";
    }
  }

  function scrollToBottom(behavior: ScrollBehavior = "auto") {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior });
  }

  function scrollAnchorToTop(anchorId: string, behavior: ScrollBehavior = "smooth") {
    const el = scrollRef.current;
    if (!el) return;
    const target = el.querySelector(`[data-msg-id="${anchorId}"]`) as HTMLElement | null;
    if (!target) return;
    const offset = 14; // keep a little air above the user turn (Perplexity-style)
    // Use rect math (offsetTop can be wrong when there are wrappers / different offsetParents).
    const elRect = el.getBoundingClientRect();
    const tRect = target.getBoundingClientRect();
    const top = Math.max(0, el.scrollTop + (tRect.top - elRect.top) - offset);
    el.scrollTo({ top, behavior });
  }

  function scheduleAnchorToTop(anchorId: string, behavior: ScrollBehavior = "smooth") {
    // Anchor needs to run *after* the message DOM node exists.
    pendingAnchorIdRef.current = anchorId;
    anchorLockRef.current = true;
    let tries = 0;
    const tick = () => {
      tries += 1;
      const el = scrollRef.current;
      if (!el) return;
      const target = el.querySelector(`[data-msg-id="${anchorId}"]`) as HTMLElement | null;
      if (target) {
        pendingAnchorIdRef.current = null;
        pendingAnchorNeedsTailRef.current = false;
        // Ensure there's enough scroll room to place the newest user turn near the top,
        // without keeping a huge permanent spacer that causes "push up" during generation.
        const offset = 14;
        // Cap to avoid creating huge blank space when the thread is short.
        const neededRaw = Math.max(
          0,
          Math.floor(el.clientHeight - target.getBoundingClientRect().height - offset - 12),
        );
        const needed = Math.min(160, neededRaw);
        setBottomPadPx((prev) => (Math.abs(prev - needed) > 8 ? needed : prev));
        scrollAnchorToTop(anchorId, behavior);
        return;
      }
      if (tries < 12) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  }

  function lastUserMsgId(msgs: ChatMsg[]): string | null {
    for (let i = msgs.length - 1; i >= 0; i--) {
      const m = msgs[i];
      if (m && m.role === "user" && typeof m.id === "string" && m.id) return m.id;
    }
    return null;
  }

  useLayoutEffect(() => {
    const pending = pendingAnchorIdRef.current;
    if (pending) {
      // If the pending anchor is the last message, anchoring would require artificial padding
      // and can create a "blank pushed" layout. Wait until there is real content below.
      if (pendingAnchorNeedsTailRef.current) {
        const idx = messages.findIndex((m) => m?.id === pending);
        if (idx >= 0 && idx >= messages.length - 1) return;
      }
      // If user was already near-bottom, shift their turn toward the top.
      // (If the target isn't mounted yet, scheduleAnchorToTop will retry.)
      scheduleAnchorToTop(pending, "smooth");
      return;
    }
    // Default behavior: stay pinned only when the user is pinned and we are not anchor-locked.
    if (pinnedToBottomRef.current && !anchorLockRef.current) scrollToBottom("auto");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, busy]);

  // When switching sessions / loading history, keep the latest user turn near the top
  // (Perplexity-style) instead of snapping to the absolute bottom.
  useLayoutEffect(() => {
    const id = lastUserMsgId(messages);
    if (!id) return;
    scheduleAnchorToTop(id, "smooth");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeId, messages.length]);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    const onScroll = () => {
      const gap = el.scrollHeight - el.scrollTop - el.clientHeight;
      pinnedToBottomRef.current = gap < 32;
      // If the user scrolls back to bottom, release the "Perplexity anchor lock".
      if (pinnedToBottomRef.current) anchorLockRef.current = false;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!streamingId) return;
    let raf = 0;
    const tick = () => {
      const el = scrollRef.current;
      if (el && pinnedToBottomRef.current && !anchorLockRef.current) {
        el.scrollTop = el.scrollHeight;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [streamingId]);

  useEffect(() => {
    if (hasHydrated.current) return;
    hasHydrated.current = true;
    try {
      const saved = safeJsonParse<StudioSession[]>(localStorage.getItem(STUDIO_SESSIONS_KEY));
      const savedActive = localStorage.getItem(STUDIO_ACTIVE_SESSION_KEY);
      if (Array.isArray(saved) && saved.length > 0) {
        const normalized = normalizeSessions(saved);
        setSessions(normalized);
        setActiveId(savedActive && normalized.some((s) => s.id === savedActive) ? savedActive : normalized[0].id);
        setDraft(null);
        return;
      }
      const first = defaultSession();
      setSessions([first]);
      setActiveId(first.id);
      setDraft(null);
      localStorage.setItem(STUDIO_SESSIONS_KEY, JSON.stringify([first]));
      localStorage.setItem(STUDIO_ACTIVE_SESSION_KEY, first.id);
    } catch {
      // ignore
    }
  }, []);

  const runIdFromUrl = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    const run = (qs.get("run") ?? "").trim();
    return run || null;
  }, [location.search]);

  useEffect(() => {
    try {
      localStorage.setItem(STUDIO_SESSIONS_KEY, JSON.stringify(sessions));
      localStorage.setItem(STUDIO_ACTIVE_SESSION_KEY, activeId);
    } catch {
      // ignore
    }
  }, [sessions, activeId]);

  useEffect(() => {
    if (!hasHydrated.current) return;
    if (!runIdFromUrl) return;
    if (busy) return;
    if (lastSeededRunRef.current === runIdFromUrl) return;

    lastSeededRunRef.current = runIdFromUrl;
    queueMicrotask(() => {
      void send(
        [
          `Analyze backtest run_id: ${runIdFromUrl}`,
          "",
          "Focus on performance, drawdowns, trade behavior, and any anomalies. If you need more context, ask what to fetch next.",
        ].join("\n"),
      );
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runIdFromUrl, busy]);

  useEffect(() => {
    function onSelect(ev: Event) {
      const e = ev as CustomEvent<{ id?: string }>;
      const id = e?.detail?.id;
      if (id && sessions.some((s) => s.id === id)) setActiveId(id);
    }
    function onNewChat() {
      newChat();
    }
    function onQuick(ev: Event) {
      const e = ev as CustomEvent<{ text?: string }>;
      const t = (e?.detail?.text ?? "").trim();
      if (t) void send(t);
    }
    window.addEventListener("aimm:studio:select", onSelect as EventListener);
    window.addEventListener("aimm:studio:newchat", onNewChat as EventListener);
    window.addEventListener("aimm:studio:quick", onQuick as EventListener);
    return () => {
      window.removeEventListener("aimm:studio:select", onSelect as EventListener);
      window.removeEventListener("aimm:studio:newchat", onNewChat as EventListener);
      window.removeEventListener("aimm:studio:quick", onQuick as EventListener);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessions, activeId, busy]);

  function newChat() {
    setError(null);
    // Draft-only: don't create/persist a session until the user actually sends input.
    const s = defaultSession();
    setDraft(s);
    setActiveId(s.id);
  }

  function selectSession(id: string) {
    setError(null);
    setDraft(null);
    setActiveId(id);
  }

  function deleteSession(id: string) {
    setError(null);
    if (draft?.id === id) {
      setDraft(null);
    }
    setSessions((prev) => {
      const next = prev.filter((s) => s.id !== id);
      if (next.length === 0) {
        const first = defaultSession();
        setActiveId(first.id);
        return [first];
      }
      if (activeId === id) {
        setActiveId(next[0].id);
      }
      return next;
    });
  }

  function openRename(id: string) {
    const s = sessions.find((x) => x.id === id);
    setRenameId(id);
    setRenameValue((s?.title || "").trim() || "New conversation");
  }

  function applyRename() {
    const id = renameId;
    if (!id) return;
    const t = renameValue.trim().replace(/\s+/g, " ");
    if (!t) return;
    setSessions((prev) => prev.map((s) => (s.id === id ? { ...s, title: t.slice(0, 52) } : s)));
    setRenameId(null);
  }

  function renameSessionIfNeeded(sessionId: string, userText: string) {
    setSessions((prev) =>
      prev.map((s) => (s.id === sessionId ? applyHeuristicTitleIfPlaceholder(s, userText) : s)),
    );
  }

  function refineSessionTitleFromLlm(sessionId: string, firstUserMessage: string) {
    const payload = firstUserMessage.slice(0, 500);
    void (async () => {
      try {
        const res = await fetch("/api/studio/suggest_title", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: payload }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) return;
        const raw = typeof (data as any)?.title === "string" ? String((data as any).title) : "";
        const title = raw.trim().replace(/\s+/g, " ");
        if (title.length < 2) return;
        setSessions((prev) =>
          prev.map((s) => {
            if (s.id !== sessionId) return s;
            const userTurns = s.messages.filter((m) => m.role === "user").length;
            if (userTurns !== 1) return s;
            return { ...s, title: title.slice(0, 52) };
          }),
        );
      } catch {
        // keep heuristic title
      }
    })();
  }

  async function send(textRaw: string) {
    const text = (textRaw ?? "").trim();
    if (!text || busy) return;
    setError(null);
    setBusy(true);

    let sessionId = active?.id ?? activeId;
    const userMsg = newMsg("user", text);
    // If we're on a draft chat, materialize it into the sessions list on first user input.
    if (draft && sessionId === draft.id) {
      const materialized: StudioSession = applyHeuristicTitleIfPlaceholder(
        { ...draft, messages: [...draft.messages, userMsg] },
        text,
      );
      sessionId = materialized.id;
      setDraft(null);
      setActiveId(materialized.id);
      setSessions((prev) => [materialized, ...prev]);
    } else {
      renameSessionIfNeeded(sessionId, text);
      setSessions((prev) =>
        prev.map((s) => (s.id === sessionId ? { ...s, messages: [...s.messages, userMsg] } : s)),
      );
    }

    const baseMsgs = (sessions.find((s) => s.id === sessionId)?.messages ?? active?.messages ?? []).slice(0);
    const nextMsgs = [...baseMsgs, userMsg];
    // Perplexity-style: after sending, pull the user's message toward the top.
    pendingAnchorIdRef.current = userMsg.id;
    pendingAnchorNeedsTailRef.current = true;
    // Prevent assistant streaming from snapping us back down immediately.
    anchorLockRef.current = true;
    pinnedToBottomRef.current = false;

    try {
      const res = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, conversation: nextMsgs.slice(-8) }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const raw = (data as any)?.error ?? (data as any)?.detail;
        const msg =
          typeof raw === "string"
            ? raw
            : raw && typeof raw === "object"
              ? JSON.stringify(raw)
              : `HTTP ${res.status}`;
        throw new Error(msg);
      }

      const steps: Step[] = Array.isArray((data as any)?.steps) ? (data as any).steps : [];
      for (const s of steps) {
        if (s.action === "navigate" && s.path) {
          navigate(s.path, { replace: false });
          break;
        }
        if ((s.action === "tool_call" || s.action === "tool_result") && (s as any).tool) {
          // Special-case: inline backtest widget.
          if (
            s.action === "tool_result" &&
            (String((s as any).tool).includes("backtests.quick_async") ||
              String((s as any).tool).includes("backtests.preset_async") ||
              String((s as any).tool).includes("backtests.demo_async"))
          ) {
            const rid = parseBacktestRunIdFromToolResult(String((s as any).text || ""));
            if (rid) {
              const marker = newMsg("assistant", `__AIMM_BACKTEST__:${rid}`);
              setSessions((prev) =>
                prev.map((ss) => (ss.id === sessionId ? { ...ss, messages: [...ss.messages, marker] } : ss)),
              );
              continue;
            }
          }
          // Otherwise, show tool events as compact system lines (agentic transparency).
          if (s.action === "tool_call") {
            setSessions((prev) =>
              prev.map((ss) =>
                ss.id === sessionId ? { ...ss, messages: [...ss.messages, newMsg("system", String((s as any).text || ""))] } : ss,
              ),
            );
          }
          continue;
        }
        if (s.action === "message" && s.text) {
          const assistantMsg = newMsg("assistant", s.text);
          setStreamingId(assistantMsg.id);
          setSessions((prev) =>
            prev.map((ss) =>
              ss.id === sessionId ? { ...ss, messages: [...ss.messages, assistantMsg] } : ss,
            ),
          );
        }
      }
      const firstUserTurn = nextMsgs.filter((m) => m.role === "user").length === 1;
      if (firstUserTurn) refineSessionTitleFromLlm(sessionId, text);
    } catch (e: any) {
      setError(e?.message || "Request failed");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    window.dispatchEvent(new CustomEvent("aimm:studio:changed"));
  }, [sessions, activeId]);

  return (
    <div className="flex-1 min-h-0 flex">
      {/* Studio-local 2nd column: sessions + actions */}
      <aside className="hidden w-72 shrink-0 border-r border-border bg-background lg:flex lg:flex-col">
        <div className="p-3 border-b border-border space-y-2">
          <button
            type="button"
            onClick={newChat}
            className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm font-medium text-foreground hover:bg-muted/70 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New chat
          </button>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => void send("onboarding")}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground hover:bg-muted/60 transition-colors"
            >
              <Zap className="h-3.5 w-3.5" />
              Onboarding
            </button>
            <button
              type="button"
              onClick={() => void send("publish to leaderboard")}
              className="inline-flex items-center justify-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-xs font-medium text-foreground hover:bg-muted/60 transition-colors"
            >
              <Zap className="h-3.5 w-3.5" />
              Publish
            </button>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={sessionFilter}
              onChange={(e) => setSessionFilter(e.target.value)}
              placeholder="Search chats…"
              className="pl-9"
            />
          </div>
        </div>

        <ScrollArea className="flex-1">
          <div className="p-2 space-y-1">
            {listSessions.length === 0 ? (
              <div className="px-3 py-6 text-sm text-muted-foreground">No chats.</div>
            ) : (
              listSessions.map((s) => {
                const isActive = s.id === activeId;
                return (
                  <div
                    key={s.id}
                    className={[
                      "group w-full overflow-hidden rounded-lg border transition-colors",
                      isActive ? "border-border bg-muted text-foreground" : "border-border bg-background hover:bg-muted/60",
                    ].join(" ")}
                  >
                    <div className="flex min-w-0 items-stretch">
                      <button
                        type="button"
                        onClick={() => selectSession(s.id)}
                        className="min-w-0 flex-1 cursor-pointer px-3 py-2 text-left"
                        title={s.title}
                      >
                        <div className="truncate text-sm font-medium">{(s.title || "").trim() || "Untitled"}</div>
                        <div className="mt-0.5 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                          <span className="truncate">{fmtDate(s.created_at_ms)}</span>
                          {/* Hide internal ids — they read like debug noise. */}
                        </div>
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            type="button"
                            onClick={(e) => e.stopPropagation()}
                            className={[
                              "h-fit self-center p-1 w-10 outline-none flex items-center justify-center text-muted-foreground hover:text-foreground",
                              "cursor-pointer transition-opacity",
                              isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100 hover:opacity-100 focus:opacity-100",
                            ].join(" ")}
                            title="Chat actions"
                            aria-label="Chat actions"
                          >
                            <EllipsisVertical className="h-4 w-4" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem
                            onSelect={() => {
                              openRename(s.id);
                            }}
                          >
                            <Pencil className="h-4 w-4" />
                            Rename
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            variant="destructive"
                            onSelect={() => {
                              setDeleteId(s.id);
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </ScrollArea>
      </aside>

      <AlertDialog open={!!deleteId} onOpenChange={(o) => (o ? null : setDeleteId(null))}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete conversation?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently remove the chat from this browser.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setDeleteId(null)}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => {
                if (!deleteId) return;
                deleteSession(deleteId);
                setDeleteId(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={!!renameId} onOpenChange={(o) => (o ? null : setRenameId(null))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename chat</DialogTitle>
            <DialogDescription>Pick a short title for this thread.</DialogDescription>
          </DialogHeader>
          <Input
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            placeholder="Untitled"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter") applyRename();
            }}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameId(null)}>
              Cancel
            </Button>
            <Button onClick={applyRename}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Main chat pane */}
      <div className="flex-1 min-w-0 flex flex-col">
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {messages.some((m) => m.role === "user") ? (
            <>
              {messages
                // Hide the “Welcome to Studio” system banner once a real thread starts.
                // The landing state already teaches this; keeping it in the thread feels dumb/noisy.
                .filter((m) => m.role !== "system")
                .map((m, idx) => (
                  isBacktestMarker(m.text) ? (
                    <div key={m.id || idx} className="px-4 py-2 sm:px-6">
                      <div className="mx-auto w-full max-w-4xl">
                        <BacktestInlineWidget runId={backtestRunIdFromMarker(m.text) || ""} />
                      </div>
                    </div>
                  ) : (
                    <ChatMessage
                      key={m.id || idx}
                      id={m.id}
                      role={m.role}
                      content={m.text}
                      timestamp={undefined}
                      stream={m.role === "assistant" && m.id === streamingId}
                      onStreamDone={() => {
                        if (m.id === streamingId) setStreamingId(null);
                      }}
                    />
                  )
                ))}
            </>
          ) : (
            <div className="mx-auto flex min-h-[calc(100vh-220px)] w-full max-w-4xl flex-col justify-center px-6 py-10">
              <div className="aimm-fade-up text-center">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Studio</div>
                <h1 className="mt-2 text-2xl font-semibold tracking-tight">Ask anything about AIMM</h1>
                <p className="mt-2 text-sm text-muted-foreground">
                  Start with onboarding, how to run a backtest, how to inspect receipts, or how to publish results.
                </p>
              </div>

              <div className="aimm-fade-up mt-8">
                <div className="rounded-2xl border border-border bg-card">
                  <ChatInput variant="panel" onSend={send} isGenerating={busy} onStop={() => setBusy(false)} />
                </div>
              </div>

              <div className="aimm-fade-up mt-6 grid gap-2 rounded-2xl border border-border bg-card p-4 sm:grid-cols-2">
                {[
                  "How do I run a quick backtest and get a run_id?",
                  "Where do I inspect receipts / iterations for a run?",
                  "How do I publish a backtest result to the leaderboard?",
                  "Show me where the tools live and what they do.",
                ].map((t) => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => void send(t)}
                    className="cursor-pointer rounded-xl border border-border bg-muted/20 px-3 py-3 text-left text-sm transition-all duration-150 hover:bg-muted/60 hover:border-border/80 hover:shadow-sm active:scale-[0.99]"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          )}

          {busy && (
            <div className="px-4 py-2 sm:px-6">
              <div className="mx-auto flex max-w-4xl items-center gap-2 text-sm text-muted-foreground">
                <div className="h-4 w-4 border-2 border-muted-foreground/40 border-t-transparent rounded-full animate-spin" />
                Thinking…
              </div>
            </div>
          )}

          {error && (
            <div className="px-4 py-3 sm:px-6">
              <div className="mx-auto max-w-4xl">
                <div className="rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  <div className="whitespace-pre-wrap break-words">{friendlyError(error)}</div>
                </div>
              </div>
            </div>
          )}

          {/* Bottom spacer: lets the newest turn scroll up near top (Perplexity-style). */}
          {messages.some((m) => m.role === "user") ? (
            <div style={{ height: bottomPadPx }} aria-hidden />
          ) : null}
        </div>

        {messages.some((m) => m.role === "user") ? (
          <ChatInput onSend={send} isGenerating={busy} onStop={() => setBusy(false)} />
        ) : null}
      </div>
    </div>
  );
}

