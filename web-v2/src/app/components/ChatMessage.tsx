import { Check, Copy, User } from "lucide-react";
import React, { useEffect, useMemo, useRef, useState } from "react";

interface ChatMessageProps {
  id?: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp?: string;
  stream?: boolean;
  onStreamDone?: () => void;
}

export default function ChatMessage({ id, role, content, timestamp, stream, onStreamDone }: ChatMessageProps) {
  const [copied, setCopied] = useState(false);
  const [revealCount, setRevealCount] = useState<number>(() => (stream && role === "assistant" ? 0 : (content || "").length));
  const rafRef = useRef<number | null>(null);
  const doneRef = useRef(false);
  const text = content || "";
  const wantsStream = Boolean(stream) && role === "assistant";

  const visibleText = useMemo(() => {
    if (!wantsStream) return text;
    return text.slice(0, Math.max(0, Math.min(text.length, revealCount)));
  }, [revealCount, text, wantsStream]);

  useEffect(() => {
    if (!wantsStream) {
      setRevealCount(text.length);
      return;
    }
    doneRef.current = false;
    setRevealCount(0);
    const charsPerSec = 90;
    let last = performance.now();
    let acc = 0;
    const tick = (now: number) => {
      const dt = Math.max(0, now - last);
      last = now;
      acc += (dt / 1000) * charsPerSec;
      if (acc >= 1) {
        const delta = Math.floor(acc);
        acc -= delta;
        setRevealCount((prev) => Math.min(text.length, prev + delta));
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    };
  }, [text, wantsStream]);

  useEffect(() => {
    if (!wantsStream) return;
    if (doneRef.current) return;
    if (revealCount >= text.length) {
      doneRef.current = true;
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
      onStreamDone?.();
    }
  }, [onStreamDone, revealCount, text.length, wantsStream]);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isUser = role === "user";
  const isSystem = role === "system";
  const compact = isUser && (content || "").trim().length <= 18 && !(content || "").includes("\n");

  function ActionButtons({ subtle }: { subtle?: boolean }) {
    return (
      <div
        className={[
          "inline-flex items-center gap-1 rounded-lg border border-border bg-background/90 p-1 shadow-sm backdrop-blur",
          subtle ? "opacity-70 hover:opacity-100 transition-opacity" : "",
        ].join(" ")}
      >
        <button
          type="button"
          onClick={handleCopy}
          className="cursor-pointer rounded-md p-1.5 transition-all hover:bg-muted/60 active:scale-[0.98]"
          title={copied ? "Copied" : "Copy"}
          aria-label="Copy message"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
        {copied ? <span className="pr-1 text-[11px] text-muted-foreground">Copied</span> : null}
      </div>
    );
  }

  return (
    <div className="group w-full px-4 py-2 sm:px-6" data-msg-id={typeof id === "string" ? id : undefined}>
      <div
        className={[
          "mx-auto flex w-full max-w-4xl items-end gap-2",
          isSystem ? "justify-center" : isUser ? "justify-end" : "justify-start",
        ].join(" ")}
      >
        {/* Show only the user avatar (bot avatar adds noise). */}
        {isSystem || !isUser ? null : (
          <div
            className={[
              "mb-1 inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border",
              isUser
                ? "order-2 border-border bg-primary text-primary-foreground"
                : "order-1 border-border bg-muted text-foreground",
            ].join(" ")}
            aria-hidden
          >
            <User className="h-4 w-4" />
          </div>
        )}

        <div
          className={[
            "flex min-w-0 flex-col",
            isSystem ? "items-center" : isUser ? "order-1 items-end flex-row-reverse gap-2" : "order-2 items-start",
          ].join(" ")}
        >
          <div
            className={[
              "relative max-w-[min(720px,90%)] rounded-2xl text-[13px] leading-relaxed",
              isSystem
                ? "max-w-[min(760px,92%)] rounded-xl border border-dashed border-border bg-muted/10 px-4 py-2.5 text-center text-muted-foreground"
                : isUser
                  ? [
                      "bg-primary text-primary-foreground shadow-sm",
                      compact ? "px-3 py-2" : "px-4 py-3",
                    ].join(" ")
                  : "border border-border bg-card px-4 py-3 text-foreground shadow-sm",
            ].join(" ")}
          >
          {timestamp && !isSystem ? (
            <div className={["mb-1 text-[10px] opacity-75", isUser ? "text-primary-foreground/80" : "text-muted-foreground"].join(" ")}>
              {timestamp}
            </div>
          ) : null}

          <div className="whitespace-pre-wrap break-words">
            {visibleText}
            {wantsStream && revealCount < text.length ? (
              <span className="ml-0.5 inline-block h-[1em] w-[0.55ch] translate-y-[1px] animate-pulse rounded-[2px] bg-foreground/40 align-baseline" />
            ) : null}
          </div>

          </div>

          {/* Assistant: Perplexity-style actions under the message (always present). */}
          {role === "assistant" ? <div className="mt-1"><ActionButtons subtle /></div> : null}

          {/* User: hover-only actions under the bubble (never covering text). */}
          {isUser ? (
            <div className="mt-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100">
              <ActionButtons />
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
