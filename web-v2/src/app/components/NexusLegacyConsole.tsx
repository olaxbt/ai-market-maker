import { useMemo } from "react";
import { useLocation, useNavigate } from "react-router";
import { Activity, LayoutGrid, Network, Radio } from "lucide-react";

import { useNexusPayload } from "../../hooks/useNexusPayload";
import { Tabs, TabsList, TabsTrigger } from "./ui/tabs";
import { NexusStarSystem } from "./NexusStarSystem";
import NexusLiveMonitorPanel from "./NexusLiveMonitorPanel";
import { AgentPromptSettingsPanel } from "./AgentPromptSettingsPanel";
import { AgentNodeAvatar } from "./AgentNodeAvatar";

function asString(v: unknown) {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function prettyTime(ts: unknown) {
  if (typeof ts === "number" && Number.isFinite(ts)) return new Date(ts * 1000).toLocaleString();
  if (typeof ts === "string" && ts) {
    const d = new Date(ts);
    if (!Number.isNaN(d.getTime())) return d.toLocaleString();
  }
  return "—";
}

function tsSec(ts: unknown): number | null {
  if (typeof ts === "number" && Number.isFinite(ts)) return ts;
  if (typeof ts === "string" && ts) {
    const d = new Date(ts);
    const ms = d.getTime();
    if (!Number.isNaN(ms)) return ms / 1000;
  }
  return null;
}

function ageLabel(sec: number | null) {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

function summarizeTraceContent(content: unknown): { chips: string[]; preview: string | null } {
  const chips: string[] = [];
  let preview: string | null = null;
  if (content == null) return { chips, preview };

  if (typeof content === "string") {
    const t = content.trim();
    preview = t.length > 360 ? `${t.slice(0, 360)}…` : t || null;
    return { chips, preview };
  }

  if (typeof content !== "object" || content === null || Array.isArray(content)) {
    try {
      preview = JSON.stringify(content).slice(0, 280);
      if (preview.length >= 280) preview = `${preview}…`;
    } catch {
      preview = null;
    }
    return { chips, preview };
  }

  const o = content as Record<string, unknown>;
  const pair =
    typeof o.pair === "string"
      ? o.pair
      : typeof o.symbol === "string"
        ? o.symbol
        : typeof o.ticker === "string"
          ? o.ticker
          : null;
  if (pair) chips.push(pair);

  if (typeof o.decision === "string") chips.push(`Decision: ${o.decision}`);
  else if (typeof o.action === "string") chips.push(`Action: ${o.action}`);

  const ctx = o.context;
  if (typeof ctx === "object" && ctx && !Array.isArray(ctx)) {
    const c = ctx as Record<string, unknown>;
    if (!pair && typeof c.pair === "string") chips.unshift(c.pair);
  }

  const tp = o.thought_process;
  if (Array.isArray(tp) && tp.length > 0) {
    const step = tp[0] as Record<string, unknown>;
    const kind =
      typeof step.kind === "string"
        ? step.kind
        : typeof step.step === "string"
          ? step.step
          : typeof step.phase === "string"
            ? step.phase
            : "thought";
    chips.push(kind);
    const reasoning =
      typeof step.reasoning === "string"
        ? step.reasoning
        : typeof step.text === "string"
          ? step.text
          : typeof step.summary === "string"
            ? step.summary
            : typeof step.content === "string"
              ? step.content
              : null;
    if (reasoning) {
      preview = reasoning.trim().length > 400 ? `${reasoning.trim().slice(0, 400)}…` : reasoning.trim();
    }
  }

  if (!preview && typeof o.note === "string") preview = o.note;
  if (!preview && typeof o.message === "string") preview = o.message;
  if (!preview && typeof o.summary === "string") preview = o.summary;

  return { chips, preview };
}

type ViewMode = "nexus" | "grid" | "monitor";

export function NexusLegacyConsole() {
  const location = useLocation();
  const navigate = useNavigate();
  const { payload, loading, error: loadError, wsConnected } = useNexusPayload();

  const viewMode = useMemo<ViewMode>(() => {
    const qs = new URLSearchParams(location.search);
    const v = (qs.get("view") ?? "").trim();
    if (v === "grid") return "grid";
    if (v === "monitor") return "monitor";
    return "nexus";
  }, [location.search]);

  const selectedNodeId = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    const n = (qs.get("node") ?? "").trim();
    return n || null;
  }, [location.search]);

  const nodes = useMemo(() => ((payload?.topology as any)?.nodes ?? []) as Array<Record<string, unknown>>, [payload]);
  const edges = useMemo(() => ((payload?.topology as any)?.edges ?? []) as Array<Record<string, unknown>>, [payload]);
  const starNodes = useMemo(
    () =>
      nodes
        .map((n) => ({
          id: asString((n as any)?.id),
          label: asString((n as any)?.label) || asString((n as any)?.id),
          status: asString((n as any)?.status),
        }))
        .filter((n) => n.id),
    [nodes],
  );
  const starEdges = useMemo(
    () =>
      edges
        .map((e) => ({
          from: asString((e as any)?.from),
          to: asString((e as any)?.to),
        }))
        .filter((e) => e.from && e.to),
    [edges],
  );
  const traces = useMemo(() => (payload?.traces ?? []) as Array<Record<string, unknown>>, [payload]);
  const messageLog = useMemo(() => {
    const m = payload?.message_log;
    return Array.isArray(m) ? (m as Array<Record<string, unknown>>) : [];
  }, [payload]);

  const lastUpdate = useMemo(() => {
    if (messageLog.length > 0) {
      const ts = messageLog[messageLog.length - 1]?.ts;
      return typeof ts === "string" ? ts : null;
    }
    if (traces.length > 0) {
      const ts = traces[traces.length - 1]?.timestamp;
      return typeof ts === "string" ? ts : null;
    }
    return null;
  }, [messageLog, traces]);

  const selectedNodeLastAge = useMemo(() => {
    if (!selectedNodeId) return null;
    let lastTs = null as number | null;
    for (const t of traces) {
      if (asString((t as any)?.node_id) !== selectedNodeId) continue;
      const ts = tsSec((t as any)?.timestamp);
      if (ts != null && (lastTs == null || ts > lastTs)) lastTs = ts;
    }
    return lastTs == null ? null : Math.max(0, Date.now() / 1000 - lastTs);
  }, [selectedNodeId, traces]);

  function setView(next: ViewMode) {
    const qs = new URLSearchParams(location.search);
    if (next === "nexus") qs.delete("view");
    else qs.set("view", next);
    navigate(`/console${qs.toString() ? `?${qs.toString()}` : ""}`, { replace: true });
  }

  return (
    <div className="flex-1 min-h-0 overflow-auto nexus-bg">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Console</p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight text-foreground">Nexus trading console</h1>
              <p className="mt-1 text-sm text-muted-foreground font-mono">
                {loadError && !loading ? (
                  <span className="text-destructive">HTTP degraded</span>
                ) : (
                  <span>HTTP ok</span>
                )}
                <span className="mx-2 opacity-50">·</span>
                <span>{wsConnected ? "stream: connected" : "stream: offline"}</span>
                <span className="mx-2 opacity-50">·</span>
                <span>{loading ? "updating…" : lastUpdate ? `last: ${new Date(lastUpdate).toLocaleTimeString()}` : "last: —"}</span>
                {selectedNodeId ? (
                  <>
                    <span className="mx-2 opacity-50">·</span>
                    <span>node {selectedNodeId}</span>
                    <span className="opacity-50"> · </span>
                    <span>age {ageLabel(selectedNodeLastAge)}</span>
                  </>
                ) : null}
              </p>
            </div>

            <Tabs value={viewMode} onValueChange={(v) => setView(v as ViewMode)}>
              <TabsList>
                <TabsTrigger value="nexus">
                  <Network className="opacity-80" />
                  Topology
                </TabsTrigger>
                <TabsTrigger value="grid">
                  <LayoutGrid className="opacity-80" />
                  Agents
                </TabsTrigger>
                <TabsTrigger value="monitor">
                  <Activity className="opacity-80" />
                  Monitor
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl space-y-3">
          {viewMode === "monitor" ? (
            <NexusLiveMonitorPanel
              nodes={nodes}
              edgeCount={edges.length}
              tracesCount={traces.length}
              wsConnected={wsConnected}
              payload={payload}
            />
          ) : viewMode === "grid" ? (
            <div className="grid gap-3 lg:grid-cols-[minmax(0,0.88fr)_minmax(0,1.12fr)]">
              <div className="nexus-panel rounded-2xl p-3">
                <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Agents</div>
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {nodes.slice(0, 18).map((n) => {
                    const id = asString((n as any)?.id);
                    const label = asString((n as any)?.label) || id;
                    const actor = asString((n as any)?.actor);
                    const status = asString((n as any)?.status);
                    const selected = selectedNodeId === id;
                    return (
                      <button
                        key={id}
                        type="button"
                        onClick={() => {
                          const qs = new URLSearchParams(location.search);
                          if (selected) qs.delete("node");
                          else qs.set("node", id);
                          navigate(`/console?${qs.toString()}`, { replace: true });
                        }}
                        className={`nexus-agent-card rounded-xl p-3 text-left transition ${
                          selected ? "ring-1 ring-[var(--nexus-glow)]/35" : "hover:ring-1 hover:ring-[var(--nexus-glow)]/20"
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <AgentNodeAvatar nodeId={id} />
                          <div className="flex min-w-0 flex-1 items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="truncate font-mono text-[12px] font-semibold text-[var(--nexus-text)]">
                                {label}
                              </div>
                              <div className="truncate font-mono text-[10px] text-[var(--nexus-muted)]">{actor || "—"}</div>
                            </div>
                            <span className="shrink-0 rounded-md border border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1 font-mono text-[9px] text-[var(--nexus-muted)]">
                              {status || "—"}
                            </span>
                          </div>
                        </div>
                        <div className="nexus-agent-card-inner-rule mt-3 pt-3">
                          <div className="font-mono text-[10px] text-[var(--nexus-muted)]">
                            click to select · prompts on right
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
              <AgentPromptSettingsPanel nodeId={selectedNodeId} />
            </div>
          ) : (
            <div className="space-y-3">
              <NexusStarSystem
                nodes={starNodes}
                edges={starEdges}
                activeNodeId={selectedNodeId}
                signalCount={traces.length}
                readyToReveal={!loading}
                playIntro={false}
              />
              <div className="nexus-panel rounded-2xl p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                    Stream ({traces.length})
                  </div>
                  <span className="inline-flex items-center gap-1 rounded-lg border border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1 text-[10px] font-mono text-[var(--nexus-muted)]">
                    <Radio className="h-3 w-3" /> {wsConnected ? "live" : "offline"}
                  </span>
                </div>
                <p className="mt-1 text-[11px] text-[var(--nexus-muted)]">
                  Showing the last 40 trace events — summary first, JSON on demand when you expand Raw payload.
                </p>
                <div className="mt-2 max-h-[520px] overflow-auto space-y-2">
                  {traces.slice(-40).reverse().map((t, idx) => {
                    const nodeId = asString((t as any)?.node_id);
                    const actorRole = asString((t as any)?.actor?.role) || asString((t as any)?.actor?.id);
                    const ts = (t as any)?.timestamp;
                    const content = (t as any)?.content;
                    const hasErr = Boolean((t as any)?.error);
                    const { chips, preview } = summarizeTraceContent(content);
                    return (
                      <div
                        key={`${asString((t as any)?.trace_id) || idx}`}
                        className={`rounded-xl border p-3 ${hasErr ? "border-[var(--nexus-danger)]/35 bg-[rgba(242,92,84,0.08)]" : "border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/35"}`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              const qs = new URLSearchParams(location.search);
                              qs.set("node", nodeId);
                              navigate(`/console?${qs.toString()}`, { replace: true });
                            }}
                            className="font-mono text-[11px] text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
                          >
                            {nodeId}
                          </button>
                          <div className="text-[10px] font-mono text-[var(--nexus-muted)]">{prettyTime(ts)}</div>
                        </div>
                        <div className="mt-1 font-mono text-[10px] text-[var(--nexus-muted)]">
                          {actorRole ? `Actor: ${actorRole}` : "—"}
                        </div>
                        {hasErr ? (
                          <div className="mt-2 text-[11px] font-mono text-[var(--nexus-danger)]">
                            {(t as any)?.error != null ? String((t as any).error) : "Error flagged on trace"}
                          </div>
                        ) : null}
                        {chips.length ? (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {chips.slice(0, 6).map((c, i) => (
                              <span
                                key={`${c}-${i}`}
                                className="rounded-md border border-[var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/60 px-2 py-0.5 font-mono text-[9px] text-[var(--nexus-text)]"
                              >
                                {c}
                              </span>
                            ))}
                          </div>
                        ) : null}
                        {preview ? (
                          <p className="mt-2 text-[11px] leading-relaxed whitespace-pre-wrap text-[var(--nexus-text)]">
                            {preview}
                          </p>
                        ) : !hasErr ? (
                          <p className="mt-2 text-[11px] text-[var(--nexus-muted)]">No readable summary — expand Raw payload.</p>
                        ) : null}
                        <details className="mt-2 group">
                          <summary className="cursor-pointer list-none font-mono text-[10px] text-[var(--nexus-muted)] hover:text-[var(--nexus-text)] [&::-webkit-details-marker]:hidden">
                            <span className="underline underline-offset-2">Raw payload</span>
                            <span className="ml-2 opacity-50 group-open:hidden">···</span>
                          </summary>
                          <pre className="mt-2 max-h-[220px] overflow-auto rounded-xl border border-[var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-3 text-[10px] text-[var(--nexus-text)]">
                            {JSON.stringify(content, null, 2)}
                          </pre>
                        </details>
                      </div>
                    );
                  })}
                  {traces.length === 0 ? <div className="text-[11px] text-[var(--nexus-muted)]">No traces yet.</div> : null}
                </div>
              </div>
            </div>
          )}

          {loadError && !loading ? (
            <div className="nexus-panel rounded-2xl px-4 py-3 text-[11px] font-mono text-[var(--nexus-danger)]">
              Failed to load traces: {loadError.message}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

