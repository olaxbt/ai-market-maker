"use client";

import { Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { BacktestLabPanel } from "@/features/backtest";
import { SupervisorPanel } from "@/features/supervisor";
import {
  AgentsConsoleView,
  NexusConsoleHeader,
  NexusDeskView,
  NexusStarSystem,
  type NexusViewMode,
} from "@/features/nexus";
import { LiveMonitorPanel } from "@/features/monitor/components/LiveMonitorPanel";
import { FutuWorkspace } from "@/features/futu/FutuWorkspace";
import { RunBacktestPrompt } from "@/components/RunBacktestPrompt";
import { LivePaperControls } from "@/components/LivePaperControls";
import { DualLaneStatus } from "@/components/DualLaneStatus";
import { useNexusPayload } from "@/hooks/useNexusPayload";
import { useNexusSignalCount } from "@/hooks/useNexusSignalCount";
import { NEXUS_BOOT_KEY } from "@/components/InitialBootOverlay";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { isBacktestRunId, parseConsoleView, researchConsoleHref } from "@/lib/consoleView";
import type { NexusPayload, Topology } from "@/types/nexus-payload";
import mockTraces from "@/data/mock-traces.json";

const EMPTY_TOPOLOGY: Topology = { nodes: [], edges: [] };
const SETUP_PAYLOAD = mockTraces as NexusPayload;

function hasBootedThisSession(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return sessionStorage.getItem(NEXUS_BOOT_KEY) === "1";
  } catch {
    return false;
  }
}

function isPortfolioView(mode: NexusViewMode): boolean {
  return mode === "portfolio" || mode === "monitor";
}

function ConsoleInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const backtestRunParam = searchParams.get("run");
  const [viewMode, setViewMode] = useState<NexusViewMode>(() =>
    parseConsoleView(searchParams.get("view"), searchParams.get("run")),
  );
  const [paperRunning, setPaperRunning] = useState(false);
  const [paperRunId, setPaperRunId] = useState<string | null>(null);
  const [followResearchId, setFollowResearchId] = useState<string | null>(null);

  // ?run=bt-* without view → Research
  useEffect(() => {
    const raw = (searchParams.get("view") || "").trim();
    const run = (searchParams.get("run") || "").trim();
    if (raw === "backtest" || raw === "supervisor") {
      router.replace(researchConsoleHref(run || null), { scroll: false });
      return;
    }
    if (raw === "monitor") {
      router.replace("/console?view=portfolio", { scroll: false });
      return;
    }
    if (!raw && isBacktestRunId(run)) {
      router.replace(researchConsoleHref(run), { scroll: false });
    }
  }, [router, searchParams]);

  useEffect(() => {
    if (viewMode === "research" || viewMode === "futu" || isPortfolioView(viewMode)) {
      setFollowResearchId(null);
    }
  }, [viewMode]);

  useEffect(() => {
    if (!followResearchId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch(`${getFlowApiOrigin()}/engine/desk`, { cache: "no-store" });
        if (!res.ok || cancelled) return;
        const data = (await res.json()) as { active_backtest_id?: string | null };
        const active = (data.active_backtest_id || "").trim();
        if (active !== followResearchId) setFollowResearchId(null);
      } catch {
        // ignore
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 4000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [followResearchId]);

  const followRunId = useMemo(() => {
    if (viewMode === "research" || viewMode === "futu") {
      return "latest-paper";
    }
    if (viewMode === "nexus" || viewMode === "grid") {
      const follow = (followResearchId || "").trim();
      if (follow) return follow;
      const rid = (paperRunId || "").trim();
      if (paperRunning && rid) return rid;
      return "latest-paper";
    }
    if (isPortfolioView(viewMode)) {
      const rid = (paperRunId || "").trim();
      if (paperRunning && rid) return rid;
      return "latest-paper";
    }
    return "latest-paper";
  }, [followResearchId, paperRunId, paperRunning, viewMode]);
  const { payload, loading, wsConnected, error: loadError, traceDataSource } =
    useNexusPayload(followRunId);
  const [hubRevealDone, setHubRevealDone] = useState(false);
  const [bootOverlayVisible, setBootOverlayVisible] = useState(false);
  const [bootBursting, setBootBursting] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useLayoutEffect(() => {
    setBootOverlayVisible(false);
    setHubRevealDone(true);
    setBootBursting(false);
    try {
      sessionStorage.setItem(NEXUS_BOOT_KEY, "1");
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    const raw = searchParams.get("view");
    const run = searchParams.get("run");
    const next = parseConsoleView(raw, run);
    setViewMode((prev) => {
      if (!(raw || "").trim() && prev === "research" && isBacktestRunId(run)) {
        return "research";
      }
      return next;
    });
  }, [searchParams]);

  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [traceLoadBannerDismissed, setTraceLoadBannerDismissed] = useState(false);
  const streamRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setTraceLoadBannerDismissed(false);
  }, [loadError]);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const agentsAutoOpenedRef = useRef(false);
  const prevViewModeRef = useRef<NexusViewMode>(viewMode);

  const metadata = payload?.metadata ?? null;
  const topology = useMemo(() => {
    if (payload?.topology?.nodes?.length) return payload.topology;
    if (SETUP_PAYLOAD.topology?.nodes?.length) return SETUP_PAYLOAD.topology;
    return EMPTY_TOPOLOGY;
  }, [payload?.topology]);
  const traces = useMemo(() => payload?.traces ?? [], [payload?.traces]);
  const agentPrompts = payload?.agent_prompts?.length
    ? payload.agent_prompts
    : SETUP_PAYLOAD.agent_prompts;
  const flowStatus = String(metadata?.status ?? "").toUpperCase();
  const sessionActive =
    paperRunning ||
    traces.length > 0 ||
    (flowStatus !== "" && flowStatus !== "IDLE" && flowStatus !== "UNKNOWN");
  const portfolioSessionActive = paperRunning;
  const showSetupPrompt =
    !sessionActive && (viewMode === "nexus" || viewMode === "grid");
  const showLivePaperBar =
    viewMode === "nexus" || viewMode === "grid" || isPortfolioView(viewMode);

  const lastUpdateIso = useMemo(() => {
    const msg = payload?.message_log;
    if (Array.isArray(msg) && msg.length > 0) {
      const ts = msg[msg.length - 1]?.ts;
      return typeof ts === "string" ? ts : null;
    }
    if (Array.isArray(traces) && traces.length > 0) {
      const ts = traces[traces.length - 1]?.timestamp;
      return typeof ts === "string" ? ts : null;
    }
    return null;
  }, [payload?.message_log, traces]);

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
    () => (selectedAgentId ? (topology.nodes.find((n) => n.id === selectedAgentId) ?? null) : null),
    [topology.nodes, selectedAgentId],
  );

  const selectedAgentPrompt = useMemo(() => {
    const rows = agentPrompts;
    if (!selectedAgentId || !rows?.length) return null;
    return rows.find((p) => p.node_id === selectedAgentId) ?? null;
  }, [agentPrompts, selectedAgentId]);

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
    const activeId =
      topology.nodes.find((n) => n.status === "ACTIVE")?.id ?? topology.nodes[0]?.id ?? null;
    if (activeId) setSelectedAgentId(activeId);
    agentsAutoOpenedRef.current = true;
  }, [viewMode, loading, topology.nodes]);

  const setCardRef = useCallback((traceId: string, el: HTMLDivElement | null) => {
    if (el) cardRefs.current.set(traceId, el);
    else cardRefs.current.delete(traceId);
  }, []);

  useEffect(() => {
    if (!selectedNodeId || tracesToShow.length === 0) return;
    const first = tracesToShow[0];
    const el = first && cardRefs.current.get(first.trace_id);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedNodeId]);

  const readyToReveal = Boolean(payload) || (!loading && Boolean(loadError)) || !bootOverlayVisible;
  useEffect(() => {
    if (!readyToReveal || hubRevealDone) return;
    const t = window.setTimeout(() => setHubRevealDone(true), 2800);
    return () => clearTimeout(t);
  }, [readyToReveal, hubRevealDone]);

  return (
    <div className="relative min-h-screen flex flex-col nexus-bg lg:h-screen lg:min-h-0 lg:overflow-hidden">
      {bootOverlayVisible ? (
        <div
          className={`fixed inset-0 z-50 transition-[background-color,opacity] duration-700 ${
            bootBursting ? "pointer-events-none bg-transparent opacity-0" : "bg-[var(--nexus-bg)] opacity-100"
          }`}
        >
          <NexusStarSystem
            nodes={[]}
            edges={[]}
            activeNodeId={null}
            signalCount={0}
            readyToReveal={readyToReveal}
            onBurstStart={() => {
              setBootBursting(true);
              setHubRevealDone(true);
            }}
            onIntroDone={() => {
              setBootOverlayVisible(false);
              setBootBursting(false);
              try {
                sessionStorage.setItem(NEXUS_BOOT_KEY, "1");
              } catch {
                // ignore
              }
            }}
            playIntro
            frameless
          />
        </div>
      ) : null}

      <NexusConsoleHeader
        metadata={
          viewMode === "research" || isPortfolioView(viewMode) ? null : metadata
        }
        viewMode={viewMode}
        wsConnected={
          viewMode === "research" || isPortfolioView(viewMode) ? false : wsConnected
        }
        loading={viewMode === "research" || isPortfolioView(viewMode) ? false : loading}
        lastUpdateIso={
          viewMode === "research" || isPortfolioView(viewMode) ? null : lastUpdateIso
        }
        traceDataSource={
          viewMode === "research" || isPortfolioView(viewMode) ? null : traceDataSource
        }
        sessionActive={
          viewMode === "research"
            ? false
            : isPortfolioView(viewMode)
              ? portfolioSessionActive
              : sessionActive
        }
      />

      <div className="relative flex min-h-0 flex-1 flex-col">
        {showLivePaperBar ? (
          <LivePaperControls
            onRunningChange={(running, rid) => {
              setPaperRunning(running);
              setPaperRunId(rid ?? null);
            }}
          />
        ) : null}
        {viewMode === "nexus" || viewMode === "grid" ? (
          <DualLaneStatus
            followingResearchId={followResearchId}
            onFollowResearch={(id) => setFollowResearchId(id)}
            onStopFollowResearch={() => setFollowResearchId(null)}
          />
        ) : null}
        {showSetupPrompt ? (
          <RunBacktestPrompt context={viewMode === "grid" ? "agents" : "flow"} />
        ) : null}

        {loadError &&
        !loading &&
        !traceLoadBannerDismissed &&
        viewMode !== "futu" &&
        viewMode !== "research" &&
        !isPortfolioView(viewMode) ? (
          <div
            className="flex shrink-0 items-center justify-center gap-3 border-b border-[color:var(--nexus-border-error)] bg-[color:var(--nexus-surface-error)] px-4 py-2 font-mono text-[11px] text-[var(--nexus-danger)]"
            role="alert"
          >
            <span className="min-w-0 flex-1 text-center">
              Live session feed unavailable ({loadError.message}). Showing the agent setup map instead.
            </span>
            <button
              type="button"
              onClick={() => setTraceLoadBannerDismissed(true)}
              className="shrink-0 rounded-md border border-[color:var(--nexus-border-error)] bg-[var(--nexus-panel)] px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-[var(--nexus-text)] hover:bg-[var(--nexus-surface)]"
            >
              Dismiss
            </button>
          </div>
        ) : null}

        {viewMode === "research" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden px-4 py-3">
              <div className="grid min-h-0 flex-1 grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)] gap-3">
                <section className="flex min-h-0 min-w-0 flex-col overflow-y-auto overflow-x-hidden rounded-2xl bg-[var(--nexus-panel)]/40 ring-1 ring-[color:var(--nexus-card-stroke)]">
                  <BacktestLabPanel embedded embeddedView="research" initialRunId={backtestRunParam} />
                </section>
                <section className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl bg-[var(--nexus-panel)]/40 ring-1 ring-[color:var(--nexus-card-stroke)]">
                  <SupervisorPanel embedded initialRunId={backtestRunParam} />
                </section>
              </div>
            </div>
          </div>
        ) : viewMode === "futu" ? (
          <div className="min-h-0 flex-1 overflow-auto">
            <FutuWorkspace />
          </div>
        ) : isPortfolioView(viewMode) ? (
          <LiveMonitorPanel sessionActive={portfolioSessionActive} />
        ) : viewMode === "grid" ? (
          <AgentsConsoleView
            nodes={topology.nodes}
            edges={topology.edges}
            traces={traces}
            agentPrompts={agentPrompts}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
            selectedAgentNode={selectedAgentNode}
            selectedAgentTraces={selectedAgentTraces}
            selectedAgentPrompt={selectedAgentPrompt}
            streaming={wsConnected && sessionActive}
          />
        ) : (
          <NexusDeskView
            nodes={topology.nodes}
            edges={topology.edges}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
            signalCount={signalCount}
            streaming={wsConnected && sessionActive}
            tracesToShow={tracesToShow}
            messageLog={payload?.message_log}
            streamRef={streamRef}
            setCardRef={setCardRef}
            readyToReveal={readyToReveal}
            revealDone={hubRevealDone}
            onIntroDone={() => setHubRevealDone(true)}
          />
        )}
      </div>
    </div>
  );
}

export default function ConsolePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-xs text-[var(--nexus-muted)]">
          Loading console…
        </div>
      }
    >
      <ConsoleInner />
    </Suspense>
  );
}
