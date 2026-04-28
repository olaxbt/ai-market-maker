import type { MessageLogEntry } from "@/types/nexus-payload";

export type BarTimelineStatus = "complete" | "running" | "error";

export type BarTimelineGroup = {
  key: string;
  barStep0: number | null;
  /** 1-based label, e.g. "Bar 3" */
  title: string;
  barTimeUtc: string | null;
  entries: MessageLogEntry[];
  status: BarTimelineStatus;
};

const LEGACY_BAR_PREFIX = /^\[bar (\d+) · ([^\]]*)\]\s*/;

/** Strip legacy `[bar n · …]` prefix from message; return cleaned text for outlines. */
export function stripLegacyBarPrefix(message: string): {
  rest: string;
  bar1?: number;
  barTime?: string;
} {
  const m = message.match(LEGACY_BAR_PREFIX);
  if (!m) return { rest: message };
  return {
    rest: message.slice(m[0].length).trim(),
    bar1: parseInt(m[1], 10),
    barTime: m[2]?.trim(),
  };
}

function entryBarMeta(e: MessageLogEntry): {
  step0: number | null;
  time: string | null;
  text: string;
} {
  if (typeof e.bar_step === "number" && !Number.isNaN(e.bar_step)) {
    return {
      step0: e.bar_step,
      time: e.bar_time_utc?.trim() || null,
      text: e.message.trim(),
    };
  }
  const { rest, bar1, barTime } = stripLegacyBarPrefix(e.message);
  if (bar1 != null && !Number.isNaN(bar1)) {
    return { step0: bar1 - 1, time: barTime || null, text: rest };
  }
  return { step0: null, time: null, text: e.message.trim() };
}

function maxBarStep(entries: MessageLogEntry[]): number | null {
  let m: number | null = null;
  for (const e of entries) {
    const { step0 } = entryBarMeta(e);
    if (step0 != null && (m === null || step0 > m)) m = step0;
  }
  return m;
}

function inferStatus(
  group: { barStep0: number | null; entries: MessageLogEntry[] },
  streaming: boolean,
  globalMaxBar: number | null,
): BarTimelineStatus {
  const lines = group.entries.map((e) => entryBarMeta(e).text.toLowerCase()).join("\n");
  const hardErr =
    group.entries.some((e) => e.kind === "error") ||
    group.entries.some((e) => /(^|\s)error:\s/i.test(entryBarMeta(e).text)) ||
    /\berror:\s/i.test(lines);
  if (hardErr) return "error";

  if (
    streaming &&
    group.barStep0 !== null &&
    globalMaxBar !== null &&
    group.barStep0 === globalMaxBar
  ) {
    return "running";
  }
  return "complete";
}

/** One short phrase per log line for collapsed bar summary. */
export function shortenOutline(text: string, max = 56): string {
  const t = text.replace(/\s+/g, " ").trim();
  if (!t) return "…";
  const cut = t.split(/(?<=[.!?])\s/)[0] ?? t;
  const s = cut.length > max ? `${cut.slice(0, max - 1)}…` : cut;
  return s;
}

/** Group message log rows by synthetic bar; order bars by step, unknown bucket last. */
export function groupBacktestMessageLog(
  entries: MessageLogEntry[],
  streaming: boolean,
): BarTimelineGroup[] {
  const sorted = [...entries].sort((a, b) => a.seq - b.seq);
  const buckets = new Map<string, MessageLogEntry[]>();
  const meta = new Map<string, { step0: number | null; time: string | null }>();

  for (const e of sorted) {
    const { step0, time } = entryBarMeta(e);
    const key = step0 !== null ? `b${step0}` : "unknown";
    if (!buckets.has(key)) {
      buckets.set(key, []);
      meta.set(key, { step0: step0, time });
    }
    buckets.get(key)!.push(e);
    const cur = meta.get(key)!;
    if (time && !cur.time) cur.time = time;
    if (step0 !== null && cur.step0 === null) cur.step0 = step0;
  }

  const globalMax = maxBarStep(sorted);

  const keys = Array.from(buckets.keys()).sort((a, b) => {
    if (a === "unknown") return 1;
    if (b === "unknown") return -1;
    const sa = meta.get(a)?.step0 ?? -1;
    const sb = meta.get(b)?.step0 ?? -1;
    return sa - sb;
  });

  return keys.map((key) => {
    const entries = buckets.get(key)!;
    const { step0, time } = meta.get(key)!;
    const title = step0 !== null ? `Bar ${step0 + 1}` : "Timeline (no bar index)";
    const g: BarTimelineGroup = {
      key,
      barStep0: step0,
      title,
      barTimeUtc: time,
      entries,
      status: "complete",
    };
    g.status = inferStatus(g, streaming, globalMax);
    return g;
  });
}
