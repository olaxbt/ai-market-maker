"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BacktestLabPanel } from "@/features/backtest";
import { SupervisorPanel } from "@/features/supervisor";
import { AgentsConsoleView, NexusConsoleHeader, NexusDeskView, NexusStarSystem, type NexusViewMode } from "@/features/nexus";
import { LiveMonitorPanel } from "@/features/monitor/components/LiveMonitorPanel";
import { useNexusPayload } from "@/hooks/useNexusPayload";
import { useNexusSignalCount } from "@/hooks/useNexusSignalCount";
import type { Topology } from "@/types/nexus-payload";

const EMPTY_TOPOLOGY: Topology = { nodes: [], edges: [] };

function NexusPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const backtestRunParam = searchParams.get("run");
  const { payload, loading, wsConnected, error: loadError } = useNexusPayload();
  const [hubRevealDone, setHubRevealDone] = useState(false);
  const [bootOverlayVisible, setBootOverlayVisible] = useState(true);
  const [bootBursting, setBootBursting] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<NexusViewMode>("nexus");

  useEffect(() => {
    const v = searchParams.get("view");
    if (v === "backtest") setViewMode("backtest");
    else if (v === "supervisor") setViewMode("supervisor");
    else if (v === "grid") setViewMode("grid");
    else if (v === "monitor") setViewMode("monitor");
    else if (v === "research") setViewMode("research");
    else setViewMode("nexus");
  }, [searchParams]);

  const handleViewModeChange = useCallback(
    (mode: NexusViewMode) => {
      setViewMode(mode);
      if (mode === "backtest") {
        router.replace("/?view=backtest", { scroll: false });
      } else if (mode === "research") {
        router.replace("/?view=research", { scroll: false });
      } else if (mode === "supervisor") {
        router.replace("/?view=supervisor", { scroll: false });
      } else if (mode === "grid") {
        router.replace("/?view=grid", { scroll: false });
      } else if (mode === "monitor") {
        router.replace("/?view=monitor", { scroll: false });
      } else {
        router.replace("/", { scroll: false });
      }
    },
    [router],
  );
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const streamRef = useRef<HTMLDivElement>(null);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const agentsAutoOpenedRef = useRef(false);
  const prevViewModeRef = useRef<NexusViewMode>(viewMode);

  const metadata = payload?.metadata ?? null;
  const topology = useMemo(
    () => payload?.topology ?? EMPTY_TOPOLOGY,
    [payload?.topology],
  );
  const traces = useMemo(() => payload?.traces ?? [], [payload?.traces]);

  const signalCount = useNexusSignalCount(payload?.message_log, traces.length);

  const tracesToShow = useMemo(() => {
    if (!selectedNodeId) return traces;
    return traces.filter((t) => t.node_id === selectedNodeId);
  }, [traces, selectedNodeId]);

  const selectedAgentTraces = useMemo(
    () => (selectedAgentId ? traces.filter((t) => t.node_id === selectedAgentId) : []),
    [traces, selectedAgentId],
  );
  const selectedAgentNode = useMemo(
    () =>
      selectedAgentId ? topology.nodes.find((n) => n.id === selectedAgentId) ?? null : null,
    [topology.nodes, selectedAgentId],
  );

  const selectedAgentPrompt = useMemo(() => {
    const rows = payload?.agent_prompts;
    if (!selectedAgentId || !rows?.length) return null;
    return rows.find((p) => p.node_id === selectedAgentId) ?? null;
  }, [payload?.agent_prompts, selectedAgentId]);

  useEffect(() => {
    const leftGrid = prevViewModeRef.current === "grid" && viewMode !== "grid";
    prevViewModeRef.current = viewMode;
    if (leftGrid) {
      setSelectedAgentId(null);
      agentsAutoOpenedRef.current = false;
    }
  }, [viewMode]);

  useEffect(() => {
    if (viewMode !== "grid" || loading || topology.nodes.length === 0) return;
    if (agentsAutoOpenedRef.current) return;
    const activeId = topology.nodes.find((n) => n.status === "ACTIVE")?.id ?? null;
    if (activeId) setSelectedAgentId(activeId);
    agentsAutoOpenedRef.current = true;
  }, [viewMode, loading, topology.nodes]);

  const viewModeTitle =
    viewMode === "nexus"
      ? "Nexus: live topology, event stream, and mesh."
      : viewMode === "grid"
        ? "Agents: pick a card; detail, traces, and prompts open in the side panel (same page)."
        : viewMode === "backtest"
          ? "Backtest: async bar replay, per-step progress, and the same FlowEvent agent traces as live runs."
          : viewMode === "research"
            ? "Research: compact backtest + supervisor (shared run id)."
          : viewMode === "monitor"
            ? "Monitor: balances, positions, and the latest system decision."
            : "Supervisor: ask questions and get an executive snapshot for a backtest run.";

  const setCardRef = useCallback((traceId: string, el: HTMLDivElement | null) => {
    if (el) cardRefs.current.set(traceId, el);
    else cardRefs.current.delete(traceId);
  }, []);

  useEffect(() => {
    if (!selectedNodeId || tracesToShow.length === 0) return;
    const first = tracesToShow[0];
    const el = first && cardRefs.current.get(first.trace_id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    // Only run this when the user changes the filter (selectedNodeId).
    // Do NOT depend on `tracesToShow` or live streaming updates will yank scroll position.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId]);

  const readyToReveal = Boolean(payload) || (!loading && Boolean(loadError));
  useEffect(() => {
    // Never "un-reveal" once visible. If intro callback is missed for any reason,
    // force reveal after a short watchdog timeout.
    if (!readyToReveal || hubRevealDone) return;
    const t = window.setTimeout(() => setHubRevealDone(true), 2800);
    return () => clearTimeout(t);
  }, [readyToReveal, hubRevealDone]);

  return (
    <div className="relative min-h-screen flex flex-col nexus-bg lg:h-screen lg:min-h-0 lg:overflow-hidden">
      {bootOverlayVisible ? (
        <div
          className={`fixed inset-0 z-50 transition-[background-color,opacity] duration-700 ${
            bootBursting
              ? "pointer-events-none bg-transparent opacity-0"
              : "bg-[var(--nexus-bg)] opacity-100"
          }`}
        >
          <NexusStarSystem
            nodes={[]}
            edges={[]}
            activeNodeId={null}
            signalCount={0}
            readyToReveal={readyToReveal}
            onBurstStart={() => {
              // Reveal dashboard *as burst begins* so the explode blends into the app.
              setBootBursting(true);
              setHubRevealDone(true);
            }}
            onIntroDone={() => {
              // Unmount overlay after burst finishes.
              setBootOverlayVisible(false);
              setBootBursting(false);
            }}
            playIntro
            frameless
          />
        </div>
      ) : null}
      <NexusConsoleHeader
        metadata={metadata}
        viewMode={viewMode}
        onViewModeChange={handleViewModeChange}
        viewModeTitle={viewModeTitle}
      />

      <div className="relative flex min-h-0 flex-1 flex-col">
        {loadError && !loading ? (
          <div
            className="pointer-events-none absolute inset-x-0 top-0 z-20 border-b border-[rgba(242,92,84,0.28)] bg-[rgba(6,8,11,0.72)] px-4 py-2 text-center font-mono text-[11px] text-[rgba(242,92,84,0.95)] backdrop-blur"
            role="alert"
          >
            Failed to load traces: {loadError.message}
          </div>
        ) : null}

        {viewMode === "backtest" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="mx-auto flex min-h-0 w-full max-w-6xl flex-1 flex-col overflow-hidden px-4 py-3">
              <BacktestLabPanel embedded initialRunId={backtestRunParam} />
            </div>
          </div>
        ) : viewMode === "research" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden px-4 py-3">
              <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] gap-3">
                <section className="min-h-0 overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45">
                  <BacktestLabPanel embedded embeddedView="research" initialRunId={backtestRunParam} />
                </section>
                <section className="min-h-0 overflow-hidden rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45 p-3">
                  <SupervisorPanel embedded initialRunId={backtestRunParam} />
                </section>
              </div>
            </div>
          </div>
        ) : viewMode === "supervisor" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-auto">
            <SupervisorPanel initialRunId={backtestRunParam} />
          </div>
        ) : viewMode === "monitor" ? (
          <LiveMonitorPanel payload={payload ?? null} fallbackRunId={backtestRunParam} />
        ) : viewMode === "grid" ? (
          <AgentsConsoleView
            nodes={topology.nodes}
            edges={topology.edges}
            traces={traces}
            agentPrompts={payload?.agent_prompts}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
            selectedAgentTraces={selectedAgentTraces}
            selectedAgentNode={selectedAgentNode}
            selectedAgentPrompt={selectedAgentPrompt}
            streaming={wsConnected}
          />
        ) : (
          <NexusDeskView
            nodes={topology.nodes}
            edges={topology.edges}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            signalCount={signalCount}
            streaming={wsConnected}
            tracesToShow={tracesToShow}
            messageLog={payload?.message_log ?? []}
            streamRef={streamRef}
            setCardRef={setCardRef}
            readyToReveal={readyToReveal}
            revealDone={hubRevealDone}
            onIntroDone={() => setHubRevealDone(true)}
          />
        )}
      </div>

      <footer className="border-t border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/80 px-4 py-2 text-[10px] text-[var(--nexus-muted)] font-mono">
        {viewMode === "backtest" || viewMode === "research" ? (
          "Backtest · preset async job · expand bars for CoT + log · equity / fills / KPIs"
        ) : (
          "metadata + topology + traces (node_id, parent_id) · streaming chain-of-thought and decision provenance"
        )}
      </footer>
    </div>
  );
}

export default function NexusPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[var(--nexus-bg)]">
          <div className="fixed inset-0 bg-[var(--nexus-bg)]">
            <div className="flex h-full w-full items-center justify-center">
              <NexusStarSystem
                nodes={[]}
                edges={[]}
                activeNodeId={null}
                signalCount={0}
                readyToReveal={false}
                playIntro
                frameless
              />
            </div>
          </div>
        </div>
      }
    >
      <NexusPageInner />
    </Suspense>
  );
}
