import { describe, expect, it } from "vitest";
import { topologyLayers } from "@/lib/topologyLayers";
import type { TopologyEdge, TopologyNode } from "@/types/nexus-payload";

function node(id: string): TopologyNode {
  return { id, actor: id, label: id, status: "PENDING" };
}

describe("topologyLayers", () => {
  it("groups parallel nodes into the same stage", () => {
    const nodes: TopologyNode[] = [node("a"), node("b"), node("c"), node("d")];
    const edges: TopologyEdge[] = [
      { from: "a", to: "b" },
      { from: "a", to: "c" },
      { from: "b", to: "d" },
      { from: "c", to: "d" },
    ];

    const layers = topologyLayers(nodes, edges);
    expect(layers.map((row) => row.map((n) => n.id))).toEqual([["a"], ["b", "c"], ["d"]]);
  });
});
