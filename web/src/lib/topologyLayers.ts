import type { TopologyEdge, TopologyNode } from "@/types/nexus-payload";

/**
 * Assign each node to a horizontal layer from edges:
 * layer(v) = max(layer(u) for u ∈ predecessors(v)) + 1, roots = 0.
 * Nodes that share the same predecessors end up on the same row (Tier-1 parallel).
 */
export function topologyLayers(nodes: TopologyNode[], edges: TopologyEdge[]): TopologyNode[][] {
  const ids = new Set(nodes.map((n) => n.id));
  if (ids.size === 0) return [];
  const idList = Array.from(ids);

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const preds = new Map<string, string[]>();
  const succs = new Map<string, string[]>();
  for (const id of idList) {
    preds.set(id, []);
    succs.set(id, []);
  }
  for (const e of edges) {
    if (!ids.has(e.from) || !ids.has(e.to)) continue;
    preds.get(e.to)!.push(e.from);
    succs.get(e.from)!.push(e.to);
  }

  const indeg = new Map<string, number>();
  for (const id of idList) indeg.set(id, preds.get(id)!.length);
  const queue = idList.filter((id) => (indeg.get(id) ?? 0) === 0);
  queue.sort((a, b) => a.localeCompare(b));

  const topo: string[] = [];
  while (queue.length) {
    const id = queue.shift()!;
    topo.push(id);
    for (const to of succs.get(id) ?? []) {
      indeg.set(to, (indeg.get(to) ?? 0) - 1);
      if (indeg.get(to) === 0) {
        queue.push(to);
        queue.sort((a, b) => a.localeCompare(b));
      }
    }
  }
  for (const id of idList) {
    if (!topo.includes(id)) topo.push(id);
  }

  const level = new Map<string, number>();
  for (const id of topo) {
    const ps = preds.get(id)!;
    const L = ps.length === 0 ? 0 : Math.max(...ps.map((p) => level.get(p) ?? 0)) + 1;
    level.set(id, L);
  }

  const maxL = Math.max(0, ...Array.from(level.values()));
  const buckets: TopologyNode[][] = Array.from({ length: maxL + 1 }, () => []);
  for (const id of topo) {
    const n = byId.get(id);
    if (n) buckets[level.get(id)!].push(n);
  }
  for (const row of buckets) {
    row.sort((a, b) => a.id.localeCompare(b.id));
  }
  return buckets.filter((row) => row.length > 0);
}
