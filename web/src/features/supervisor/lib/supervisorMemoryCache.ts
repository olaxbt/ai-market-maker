import type { PortfolioManagerSnapshotResponse as PmSnapshotResponse } from "@/types/portfolio-manager";

type ChatMsg = {
  id: string;
  role: "user" | "assistant";
  text: string;
  ts: number;
};

type Entry = {
  key: string;
  updatedAt: number;
  snapshot: PmSnapshotResponse | null;
  messages: ChatMsg[];
};

const MAX_ENTRIES = 8;
const MAX_MESSAGES = 60;
const MAX_TEXT_CHARS = 80_000;

function clampMessages(msgs: ChatMsg[]): ChatMsg[] {
  let out = msgs.slice(-MAX_MESSAGES);
  // Hard cap total text to avoid runaway memory (streaming can create huge replies).
  let total = 0;
  for (let i = out.length - 1; i >= 0; i--) {
    total += (out[i]?.text || "").length;
    if (total > MAX_TEXT_CHARS) {
      out = out.slice(i + 1);
      break;
    }
  }
  return out;
}

class SupervisorMemoryCache {
  private map = new Map<string, Entry>();

  get(key: string): Entry | null {
    const e = this.map.get(key) || null;
    if (!e) return null;
    // Touch LRU
    this.map.delete(key);
    this.map.set(key, e);
    return e;
  }

  set(key: string, patch: Omit<Entry, "key" | "updatedAt">): void {
    const entry: Entry = {
      key,
      updatedAt: Date.now(),
      snapshot: patch.snapshot,
      messages: clampMessages(patch.messages),
    };
    if (this.map.has(key)) this.map.delete(key);
    this.map.set(key, entry);

    while (this.map.size > MAX_ENTRIES) {
      const oldestKey = this.map.keys().next().value as string | undefined;
      if (!oldestKey) break;
      this.map.delete(oldestKey);
    }
  }
}

export const supervisorMemoryCache = new SupervisorMemoryCache();

