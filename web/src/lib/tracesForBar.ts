import type { BarTimelineGroup } from "@/lib/groupBacktestMessageLog";
import type { NexusTrace } from "@/types/nexus-payload";

/** Traces belonging to a bar: prefer `trace_id` links from the message log, else `bar_step` on traces. */
export function tracesForBarGroup(g: BarTimelineGroup, all: NexusTrace[]): NexusTrace[] {
  const ids = new Set(
    g.entries.map((e) => e.trace_id).filter((x): x is string => typeof x === "string" && x.length > 0),
  );
  let list: NexusTrace[];
  if (ids.size > 0) {
    list = all.filter((t) => ids.has(t.trace_id));
  } else if (g.barStep0 !== null) {
    list = all.filter((t) => typeof t.bar_step === "number" && t.bar_step === g.barStep0);
  } else {
    list = [];
  }
  return [...list].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime(),
  );
}
