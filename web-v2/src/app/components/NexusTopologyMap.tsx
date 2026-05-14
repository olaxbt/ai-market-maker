import { useEffect, useMemo, useRef, useState } from "react";

type NodeLike = { id?: unknown; label?: unknown; status?: unknown; actor?: unknown; summary?: unknown };
type EdgeLike = { from?: unknown; to?: unknown; source?: unknown; target?: unknown };

function asString(v: unknown) {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function normalizeEdges(edges: Array<Record<string, unknown>>): Array<{ from: string; to: string }> {
  const out: Array<{ from: string; to: string }> = [];
  for (const e of edges as EdgeLike[]) {
    const from = asString((e as any)?.from ?? (e as any)?.source);
    const to = asString((e as any)?.to ?? (e as any)?.target);
    if (!from || !to) continue;
    out.push({ from, to });
  }
  return out;
}

function statusKind(status: string) {
  const s = (status || "").toUpperCase();
  if (s === "FAILED" || s === "ERROR") return "bad";
  if (s === "ACTIVE" || s === "RUNNING" || s === "OK") return "ok";
  if (s === "COMPLETED") return "done";
  return "idle";
}

function tsToSec(ts: unknown): number | null {
  if (typeof ts === "number" && Number.isFinite(ts)) return ts;
  if (typeof ts === "string" && ts) {
    const d = new Date(ts);
    const ms = d.getTime();
    if (!Number.isNaN(ms)) return ms / 1000;
  }
  return null;
}

function clamp(n: number, a: number, b: number) {
  return Math.max(a, Math.min(b, n));
}

function prettyAge(sec: number | null) {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

type TopoNode = { id: string; label: string; status: string; actor: string; summary: string };

export function NexusTopologyMap({
  nodes,
  edges,
  traces,
  selectedNodeId,
  onSelectNodeId,
}: {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  traces: Array<Record<string, unknown>>;
  selectedNodeId: string | null;
  onSelectNodeId: (id: string | null) => void;
}) {
  const normEdges = useMemo(() => normalizeEdges(edges), [edges]);

  const topoNodes: TopoNode[] = useMemo(() => {
    const out: TopoNode[] = [];
    for (const n of nodes as NodeLike[]) {
      const id = asString((n as any)?.id);
      if (!id) continue;
      out.push({
        id,
        label: asString((n as any)?.label) || id,
        status: asString((n as any)?.status),
        actor: asString((n as any)?.actor),
        summary: asString((n as any)?.summary),
      });
    }
    out.sort((a, b) => a.id.localeCompare(b.id));
    return out;
  }, [nodes]);

  const nodeById = useMemo(() => new Map(topoNodes.map((n) => [n.id, n])), [topoNodes]);

  const nodeIds = useMemo(() => topoNodes.map((n) => n.id), [topoNodes]);
  const idSet = useMemo(() => new Set(nodeIds), [nodeIds]);

  const filteredEdges = useMemo(() => normEdges.filter((e) => idSet.has(e.from) && idSet.has(e.to)), [normEdges, idSet]);

  const lastTraceByNode = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of traces) {
      const nodeId = asString((t as any)?.node_id);
      const ts = tsToSec((t as any)?.timestamp);
      if (!nodeId || ts == null) continue;
      const prev = m.get(nodeId);
      if (prev == null || ts > prev) m.set(nodeId, ts);
    }
    return m;
  }, [traces]);

  const [nowSec, setNowSec] = useState(() => Date.now() / 1000);
  useEffect(() => {
    const id = window.setInterval(() => setNowSec(Date.now() / 1000), 1200);
    return () => window.clearInterval(id);
  }, []);

  const activityScoreByNode = useMemo(() => {
    const m = new Map<string, number>();
    for (const id of nodeIds) {
      const last = lastTraceByNode.get(id) ?? null;
      if (last == null) {
        m.set(id, 0);
        continue;
      }
      const age = Math.max(0, nowSec - last);
      m.set(id, Math.exp(-age / 120));
    }
    return m;
  }, [lastTraceByNode, nodeIds, nowSec]);

  const levels = useMemo(() => {
    // Layered layout using indegree roots + relaxation (handles cycles).
    const indeg = new Map<string, number>(nodeIds.map((id) => [id, 0]));
    const out = new Map<string, string[]>();
    for (const e of filteredEdges) {
      indeg.set(e.to, (indeg.get(e.to) ?? 0) + 1);
      out.set(e.from, [...(out.get(e.from) ?? []), e.to]);
    }
    const roots = nodeIds.filter((id) => (indeg.get(id) ?? 0) === 0);
    const depth = new Map<string, number>();
    const q: string[] = roots.length ? roots.slice() : nodeIds.slice(0, 1);
    for (const r of q) depth.set(r, 0);
    while (q.length) {
      const cur = q.shift()!;
      const d = depth.get(cur) ?? 0;
      for (const nxt of out.get(cur) ?? []) {
        const nd = Math.max(depth.get(nxt) ?? 0, d + 1);
        if ((depth.get(nxt) ?? -1) < nd) {
          depth.set(nxt, nd);
          q.push(nxt);
        }
      }
    }
    // Ensure all nodes have a depth, then relax a bit to reduce crossings.
    for (const id of nodeIds) if (!depth.has(id)) depth.set(id, 0);
    for (let it = 0; it < 6; it++) {
      for (const e of filteredEdges) {
        const a = depth.get(e.from) ?? 0;
        const b = depth.get(e.to) ?? 0;
        if (b <= a) depth.set(e.to, a + 1);
      }
    }
    let max = 0;
    for (const d of depth.values()) max = Math.max(max, d);
    const cols: string[][] = Array.from({ length: max + 1 }, () => []);
    for (const id of nodeIds) {
      cols[depth.get(id) ?? 0].push(id);
    }
    for (const col of cols) col.sort();
    return cols;
  }, [filteredEdges, nodeIds]);

  const positions = useMemo(() => {
    const cols = levels.filter((c) => c.length > 0);
    const colCount = Math.max(1, cols.length);
    const xMin = 6;
    const xMax = 94;
    const yMin = 10;
    const yMax = 92;
    const pos = new Map<string, { x: number; y: number }>();
    cols.forEach((col, ci) => {
      const x = colCount === 1 ? 50 : xMin + (ci / (colCount - 1)) * (xMax - xMin);
      const n = col.length;
      col.forEach((id, i) => {
        const y = n === 1 ? (yMin + yMax) / 2 : yMin + (i / (n - 1)) * (yMax - yMin);
        pos.set(id, { x, y });
      });
    });
    return pos;
  }, [levels]);

  const counts = useMemo(() => {
    let active = 0;
    let degraded = 0;
    let recent = 0;
    for (const n of topoNodes) {
      const k = statusKind(n.status);
      if (k === "ok") active++;
      if (k === "bad") degraded++;
      if ((activityScoreByNode.get(n.id) ?? 0) > 0.35) recent++;
    }
    return { total: topoNodes.length, active, degraded, recent };
  }, [activityScoreByNode, topoNodes]);

  const wrapRef = useRef<HTMLDivElement>(null);
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null);

  return (
    <div ref={wrapRef} className="relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="absolute inset-0 nexus-opsmesh-bg" aria-hidden="true" />

      <div className="relative px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Topology map</div>
            <div className="mt-0.5 text-sm text-muted-foreground">
              Nodes <span className="text-foreground">{counts.total}</span>
              <span className="mx-2 text-muted-foreground/40">•</span>
              Active <span className="font-mono text-foreground">{counts.active}</span>
              <span className="mx-2 text-muted-foreground/40">•</span>
              Degraded <span className="font-mono text-foreground">{counts.degraded}</span>
              <span className="mx-2 text-muted-foreground/40">•</span>
              Recent <span className="font-mono text-foreground">{counts.recent}</span>
            </div>
          </div>
          <div className="text-[11px] text-muted-foreground">clear edges · readable labels · click to select</div>
        </div>
      </div>

      <div className="relative px-3 pb-3">
        <svg className="h-[260px] w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <defs>
            <linearGradient id="mapEdge" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.38)" />
              <stop offset="100%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.14)" />
            </linearGradient>
            <marker id="mapArrow" markerWidth="7" markerHeight="7" refX="6.2" refY="3.5" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L7,3.5 L0,7 z" fill="rgba(var(--nexus-stars-accent-rgb), 0.55)" />
            </marker>
          </defs>

          {/* edges */}
          <g>
            {filteredEdges.slice(0, 520).map((e, i) => {
              const a = positions.get(e.from);
              const b = positions.get(e.to);
              if (!a || !b) return null;
              const hot = (activityScoreByNode.get(e.from) ?? 0) > 0.45 || (activityScoreByNode.get(e.to) ?? 0) > 0.45;
              const dx = b.x - a.x;
              const cx1 = a.x + dx * 0.35;
              const cx2 = a.x + dx * 0.7;
              const d = `M ${a.x} ${a.y} C ${cx1} ${a.y}, ${cx2} ${b.y}, ${b.x} ${b.y}`;
              return (
                <path
                  key={`${e.from}:${e.to}:${i}`}
                  d={d}
                  fill="none"
                  stroke="url(#mapEdge)"
                  strokeWidth={hot ? 0.42 : 0.32}
                  opacity={hot ? 1 : 0.75}
                  markerEnd="url(#mapArrow)"
                  className={hot ? "nexus-opsmesh-edge-hot" : undefined}
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </g>

          {/* nodes */}
          <g>
            {topoNodes.map((n) => {
              const p = positions.get(n.id);
              if (!p) return null;
              const score = activityScoreByNode.get(n.id) ?? 0;
              const k = statusKind(n.status);
              const selected = selectedNodeId === n.id;
              const hovered = hoverId === n.id;
              const r = 1.4 + score * 2.6 + (selected ? 1.0 : 0) + (hovered ? 0.5 : 0);
              const fill =
                k === "bad"
                  ? "rgba(var(--nexus-stars-bad-rgb), 0.95)"
                  : k === "ok"
                    ? "rgba(var(--nexus-stars-accent-rgb), 0.95)"
                    : k === "done"
                      ? "rgba(99,102,241,0.92)"
                      : "rgba(var(--nexus-stars-dust-rgb), 0.72)";
              const halo =
                k === "bad"
                  ? "rgba(var(--nexus-stars-bad-rgb), 0.10)"
                  : "rgba(var(--nexus-stars-accent-rgb), 0.08)";
              return (
                <g
                  key={n.id}
                  onMouseMove={(ev) => {
                    const box = wrapRef.current?.getBoundingClientRect();
                    if (!box) return;
                    setHoverId(n.id);
                    setTooltip({ x: ev.clientX - box.left, y: ev.clientY - box.top });
                  }}
                  onMouseLeave={() => {
                    setHoverId((cur) => (cur === n.id ? null : cur));
                    setTooltip(null);
                  }}
                  onClick={() => onSelectNodeId(selected ? null : n.id)}
                  style={{ cursor: "pointer" }}
                >
                  {(selected || hovered || score > 0.55 || k === "bad") && (
                    <circle cx={p.x} cy={p.y} r={r * 2.7} fill={halo} className="nexus-opsmesh-pulse" />
                  )}
                  <circle cx={p.x} cy={p.y} r={r} fill={fill} />
                  <text
                    x={p.x + r + 0.8}
                    y={p.y + 0.8}
                    fontSize="2.6"
                    fill="rgba(var(--foreground), 0.75)"
                  >
                    {n.label}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {hoverId && tooltip ? (
          <div
            className="pointer-events-none absolute z-10 w-[320px] rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg"
            style={{
              left: clamp(tooltip.x + 10, 8, (wrapRef.current?.clientWidth ?? 0) - 340),
              top: clamp(tooltip.y - 10, 8, (wrapRef.current?.clientHeight ?? 0) - 120),
            }}
          >
            {(() => {
              const n = nodeById.get(hoverId);
              if (!n) return null;
              const last = lastTraceByNode.get(hoverId) ?? null;
              const age = last == null ? null : Math.max(0, Date.now() / 1000 - last);
              return (
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">{n.label}</div>
                      <div className="truncate font-mono text-[11px] text-muted-foreground">{n.id}</div>
                    </div>
                    <div className="shrink-0 rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[10px] text-muted-foreground">
                      {n.status || "—"}
                    </div>
                  </div>
                  <div className="text-muted-foreground">
                    {n.actor ? (
                      <>
                        <span className="text-muted-foreground">actor</span>{" "}
                        <span className="font-mono text-foreground/90">{n.actor}</span>
                      </>
                    ) : (
                      "—"
                    )}
                    <span className="mx-2 text-muted-foreground/40">•</span>
                    <span className="text-muted-foreground">last event</span>{" "}
                    <span className="font-mono text-foreground/90">{prettyAge(age)}</span>
                  </div>
                  {n.summary ? <div className="line-clamp-3 text-muted-foreground">{n.summary}</div> : null}
                </div>
              );
            })()}
          </div>
        ) : null}
      </div>
    </div>
  );
}

