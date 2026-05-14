import { Send, Square } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  isGenerating?: boolean;
  onStop?: () => void;
  variant?: "dock" | "panel";
}

export default function ChatInput({ onSend, isGenerating = false, onStop, variant = "dock" }: ChatInputProps) {
  const [message, setMessage] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (message.trim() && !isGenerating) {
      onSend(message.trim());
      setMessage("");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = textareaRef.current.scrollHeight + "px";
    }
  }, [message]);

  return (
    <div className={variant === "dock" ? "border-t border-border bg-background" : "bg-transparent"}>
      <div className={variant === "dock" ? "mx-auto max-w-4xl p-4" : "w-full p-4"}>
        <form onSubmit={handleSubmit} className="relative">
          <div className="relative flex items-end gap-2 rounded-2xl border border-border bg-input-background focus-within:ring-2 focus-within:ring-ring/20">
            <textarea
              ref={textareaRef}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask AI anything..."
              className="flex-1 resize-none bg-transparent px-4 py-4 pr-14 outline-none min-h-[64px] max-h-[240px]"
              rows={1}
            />

            {isGenerating ? (
              <button
                type="button"
                onClick={onStop}
                className="cursor-pointer absolute right-3 bottom-3 inline-flex h-9 w-9 items-center justify-center rounded-full bg-destructive text-destructive-foreground shadow-sm hover:opacity-90 transition-opacity"
                title="Stop generating"
              >
                <Square className="h-4 w-4 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                disabled={!message.trim()}
                className="cursor-pointer absolute right-3 bottom-3 p-2 rounded-lg bg-primary text-primary-foreground hover:opacity-90 transition-opacity disabled:opacity-40 disabled:cursor-not-allowed"
                title="Send message"
              >
                <Send className="w-4 h-4" />
              </button>
            )}
          </div>

          <div className="mt-2 text-xs text-muted-foreground text-center">Press Enter to send, Shift+Enter for new line</div>
        </form>
      </div>
    </div>
  );
}
