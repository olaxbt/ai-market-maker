import mockTraces from "@/data/mock-traces.json";
import { ClientAgentDetailPage } from "./ClientAgentDetailPage";

/** Optional deep link / bookmark; primary UX is inline on the home dashboard Agents view. */
export function generateStaticParams() {
  const nodes = mockTraces?.topology?.nodes ?? [];
  return nodes.map((n) => ({ nodeId: String(n.id) }));
}

export default function AgentDetailPage({ params }: { params: { nodeId: string } }) {
  const nodeId = decodeURIComponent(params.nodeId);
  return <ClientAgentDetailPage nodeId={nodeId} />;
}
