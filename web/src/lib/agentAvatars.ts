import type { StaticImageData } from "next/image";

import alpha from "@/assets/avatars/alpha.jpg";
import execution from "@/assets/avatars/execution.jpg";
import institutional from "@/assets/avatars/insitiutional.jpg";
import liquidity from "@/assets/avatars/liquidity.jpg";
import quant from "@/assets/avatars/quant.jpg";
import risk from "@/assets/avatars/risk.jpg";
import sentiment from "@/assets/avatars/sentiment.jpg";
import signal from "@/assets/avatars/signal.jpg";
import statistical from "@/assets/avatars/statistical.jpg";

/** Maps pipeline node ids (`n1`–`n9`) to portrait assets under `assets/avatars`. */
const AVATAR_BY_NODE_ID: Record<string, StaticImageData> = {
  n1: signal,
  n2: liquidity,
  n3: statistical,
  n4: sentiment,
  n5: quant,
  n6: alpha,
  n7: risk,
  n8: institutional,
  n9: execution,
};

/** Fallback order when `node_id` is unknown. */
const PIPELINE_ORDER: StaticImageData[] = [
  signal,
  liquidity,
  statistical,
  sentiment,
  quant,
  alpha,
  risk,
  institutional,
  execution,
];

function fallbackIndex(nodeId: string): number {
  let hash = 0;
  for (let i = 0; i < nodeId.length; i++) {
    hash = (hash * 33 + nodeId.charCodeAt(i)) >>> 0;
  }
  return hash % PIPELINE_ORDER.length;
}

/**
 * Portrait for this agent. Prefers explicit n1–n9 mapping; otherwise stable pick from pipeline set.
 */
export function agentAvatarStaticSrc(nodeId: string): StaticImageData {
  const direct = AVATAR_BY_NODE_ID[nodeId];
  if (direct) return direct;
  return PIPELINE_ORDER[fallbackIndex(nodeId)] ?? signal;
}
