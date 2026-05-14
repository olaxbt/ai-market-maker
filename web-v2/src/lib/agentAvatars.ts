/**
 * Portrait paths under `web-v2/public/agent-avatars/` (ported from Next `web/src/assets/avatars`).
 * Matches NODE_REGISTRY ids in Flow payload (`n0`–`n17`).
 */
const PIPELINE_FALLBACK_ORDER = [
  "signal.jpg",
  "liquidity.jpg",
  "statistical.jpg",
  "sentiment.jpg",
  "quant.jpg",
  "alpha.jpg",
  "risk.jpg",
  "insitiutional.jpg",
  "execution.jpg",
] as const;

const AVATAR_FILE_BY_NODE_ID: Record<string, string> = {
  n0: "marco.jpg",
  n1: "signal.jpg",
  n2: "marco.jpg",
  n3: "narrative.jpg",
  n4: "pattern.png",
  n5: "statistical.jpg",
  n6: "quant.jpg",
  n7: "retiail.jpg",
  n8: "bull.jpg",
  n9: "whale.jpg",
  n10: "liquidity.jpg",
  n11: "risk.jpg",
  n12: "bear.jpg",
  n13: "sentiment.jpg",
  n14: "alpha.jpg",
  n15: "bear.jpg",
  n16: "execution.jpg",
  n17: "insitiutional.jpg",
};

function fallbackIndex(nodeId: string): number {
  let hash = 0;
  for (let i = 0; i < nodeId.length; i++) {
    hash = (hash * 33 + nodeId.charCodeAt(i)) >>> 0;
  }
  return hash % PIPELINE_FALLBACK_ORDER.length;
}

/** Public URL (Vite `public/`) for this pipeline node. */
export function agentAvatarPublicPath(nodeId: string): string {
  const id = (nodeId ?? "").trim();
  const file = AVATAR_FILE_BY_NODE_ID[id] ?? PIPELINE_FALLBACK_ORDER[fallbackIndex(id)] ?? "signal.jpg";
  return `/agent-avatars/${file}`;
}
