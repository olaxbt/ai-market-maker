import type { NexusTrace, TopologyEdge, TopologyNode } from "@/types/nexus-payload";

const MAX_LEN = 110;

function truncate(s: string, max = MAX_LEN): string {
  const t = s.trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 1)}…`;
}

/**
 * One deduped line for “what just happened” — avoids repeating signal chips + thought text.
 */
export function latestBeat(trace: NexusTrace | undefined): string | null {
  if (!trace?.content) return null;
  const c = trace.content;

  if (c.proposal?.action) {
    const p = c.proposal.params;
    let extra = "";
    if (p?.amount != null) {
      extra += ` · ${String(p.amount)}`;
      if (p?.unit != null) extra += ` ${String(p.unit)}`;
    }
    if (p?.price != null) extra += ` @ $${p.price}`;
    return truncate(`${c.proposal.action}${extra}`);
  }

  if (c.veto_status?.status) {
    const r = c.veto_status.reason ? ` — ${truncate(c.veto_status.reason, 48)}` : "";
    return truncate(`Risk · ${c.veto_status.status}${r}`);
  }

  if (c.formula != null && typeof c.formula === "object") {
    const fo = c.formula as { name?: string; latex?: string; computed?: string };
    if (fo.computed) return truncate(fo.computed);
    if (fo.name) return truncate(fo.name);
    if (fo.latex) return truncate(fo.latex, 80);
  }
  if (typeof c.formula === "string" && c.formula) return truncate(c.formula, 90);

  const sig = c.signal ?? c.context?.signal;
  const conf = c.confidence ?? c.context?.confidence;
  const pair = c.context && typeof c.context === "object" && "pair" in c.context ? String((c.context as { pair?: string }).pair ?? "") : "";

  if (sig != null) {
    const confStr = conf != null ? ` · ${(Number(conf) * 100).toFixed(0)}% conf` : "";
    const pairStr = pair ? `${pair} · ` : "";
    return truncate(`${pairStr}${String(sig)}${confStr}`);
  }

  const steps = c.thought_process;
  const last = steps?.length ? steps[steps.length - 1] : undefined;
  if (last) {
    return truncate(`${last.label}: ${last.detail}`);
  }

  return null;
}

/** First outgoing hop label(s) for pipeline context. */
export function nextHopSummary(nodeId: string, edges: TopologyEdge[], byId: Map<string, TopologyNode>): string | null {
  const outs = edges.filter((e) => e.from === nodeId).map((e) => e.to);
  if (outs.length === 0) return null;
  const labels = outs.map((id) => byId.get(id)?.label ?? id);
  if (labels.length === 1) return labels[0]!;
  return `${labels[0]} +${labels.length - 1}`;
}

/** True when this node has no outgoing edges in the topology (only meaningful if `edges` is non-empty). */
export function isPipelineSink(nodeId: string, edges: TopologyEdge[]): boolean {
  if (edges.length === 0) return false;
  return !edges.some((e) => e.from === nodeId);
}
