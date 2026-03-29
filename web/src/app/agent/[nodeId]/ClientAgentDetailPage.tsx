"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AgentDetailPanel } from "@/components/AgentDetailPanel";
import mockTraces from "@/data/mock-traces.json";
import type { NexusPayload } from "@/types/nexus-payload";

export function ClientAgentDetailPage({ nodeId }: { nodeId: string }) {
  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const useMock = process.env.NEXT_PUBLIC_USE_MOCK === "1";
    if (useMock) {
      setPayload(mockTraces as NexusPayload);
      setLoading(false);
      return;
    }

    fetch("/api/traces")
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error("Failed to load"))))
      .then((data: NexusPayload) => {
        setPayload(data);
        setLoading(false);
      })
      .catch(() => {
        setPayload(null);
        setLoading(false);
      });
  }, []);

  const node = useMemo(
    () => payload?.topology.nodes.find((n) => n.id === nodeId) ?? null,
    [payload, nodeId],
  );
  const traces = useMemo(
    () => (payload?.traces ?? []).filter((t) => t.node_id === nodeId),
    [payload, nodeId],
  );
  const promptDefaults = useMemo(
    () => payload?.agent_prompts?.find((p) => p.node_id === nodeId) ?? null,
    [payload?.agent_prompts, nodeId],
  );

  return (
    <div className="flex min-h-screen flex-col nexus-bg">
      <header className="shrink-0 border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 px-4 py-3 backdrop-blur-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
            Standalone link — prefer <span className="text-slate-300">Agents</span> on the main
            dashboard for inline editing.
          </p>
          <Link
            href="/"
            className="rounded border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/70 px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-slate-200 hover:border-[var(--nexus-glow)]/50"
          >
            ← Dashboard
          </Link>
        </div>
      </header>
      <div className="min-h-0 flex-1">
        <AgentDetailPanel
          nodeId={nodeId}
          node={node}
          traces={traces}
          promptDefaults={promptDefaults}
          loading={loading}
          variant="page"
        />
      </div>
    </div>
  );
}

