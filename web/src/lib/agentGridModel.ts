import type { NexusTrace, TopologyNode } from "@/types/nexus-payload";

export type AgentRuntimeHealth = "RUNNING" | "HOT" | "WARM" | "STANDBY";

export interface AgentTraceIndex {
  traceCountByNode: Map<string, number>;
  lastTsByNode: Map<string, string>;
  lastTraceByNode: Map<string, NexusTrace>;
  latestGlobalTs: string | undefined;
}

/** Aggregate trace timestamps per node for agent cards (pure, testable). */
export function buildAgentTraceIndex(traces: NexusTrace[]): AgentTraceIndex {
  const traceCountByNode = new Map<string, number>();
  const lastTsByNode = new Map<string, string>();
  const lastTraceByNode = new Map<string, NexusTrace>();

  for (const t of traces) {
    traceCountByNode.set(t.node_id, (traceCountByNode.get(t.node_id) ?? 0) + 1);
    const prev = lastTsByNode.get(t.node_id);
    if (!prev || t.timestamp > prev) {
      lastTsByNode.set(t.node_id, t.timestamp);
      lastTraceByNode.set(t.node_id, t);
    }
  }

  const latestGlobalTs = traces.reduce<string | undefined>(
    (acc, t) => (acc == null || t.timestamp > acc ? t.timestamp : acc),
    undefined,
  );

  return { traceCountByNode, lastTsByNode, lastTraceByNode, latestGlobalTs };
}

export function runtimeHealth(
  node: TopologyNode,
  latestNodeTs: string | undefined,
  latestGlobalTs: string | undefined,
): AgentRuntimeHealth {
  if (node.status === "ACTIVE") return "RUNNING";
  if (!latestNodeTs) return "STANDBY";
  if (!latestGlobalTs) return "WARM";
  const deltaMs = new Date(latestGlobalTs).getTime() - new Date(latestNodeTs).getTime();
  if (deltaMs <= 3000) return "HOT";
  return "WARM";
}
