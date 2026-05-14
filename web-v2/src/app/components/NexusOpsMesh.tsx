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

function hash01(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const u = h >>> 0;
  return (u % 1_000_000) / 1_000_000;
}

function initialPositions(ids: string[]) {
  const margin = 10;
  return ids.map((id) => {
    const a = hash01(`${id}:x`);
    const b = hash01(`${id}:y`);
    return {
      id,
      x: margin + a * (100 - margin * 2),
      y: margin + b * (100 - margin * 2),
    };
  });
}

function prettyAge(sec: number | null) {
  if (sec == null || !Number.isFinite(sec) || sec < 0) return "—";
  if (sec < 60) return `${Math.round(sec)}s`;
  if (sec < 3600) return `${Math.round(sec / 60)}m`;
  return `${(sec / 3600).toFixed(1)}h`;
}

type MeshFilter = "all" | "active" | "degraded" | "recent";

export function NexusOpsMesh({
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
  const nodeIds = useMemo(() => {
    const ids = (nodes as NodeLike[]).map((n) => asString((n as any)?.id)).filter(Boolean);
    return ids.slice().sort();
  }, [nodes]);
  const normEdges = useMemo(() => normalizeEdges(edges), [edges]);

  const nodeById = useMemo(() => {
    const m = new Map<string, NodeLike>();
    for (const n of nodes as NodeLike[]) {
      const id = asString((n as any)?.id);
      if (!id) continue;
      m.set(id, n);
    }
    return m;
  }, [nodes]);

  const lastTraceByNode = useMemo(() => {
    const m = new Map<string, number>();
    for (const t of traces) {
      const nodeId = asString((t as any)?.node_id);
      const ts = (t as any)?.timestamp;
      const tsSec = typeof ts === "number" && Number.isFinite(ts) ? ts : null;
      if (!nodeId || tsSec == null) continue;
      const prev = m.get(nodeId);
      if (prev == null || tsSec > prev) m.set(nodeId, tsSec);
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
      // Fast decay: “hot” within a couple minutes.
      const score = Math.exp(-age / 120);
      m.set(id, score);
    }
    return m;
  }, [lastTraceByNode, nodeIds, nowSec]);

  const [filter, setFilter] = useState<MeshFilter>("all");
  const [hoverId, setHoverId] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Keep selection visible even when user switches filters.
    if (!selectedNodeId) return;
    setFilter("all");
  }, [selectedNodeId]);

  const placed = useMemo(() => {
    // Lightweight relaxation to reduce edge crossings a bit (deterministic start).
    const pts = initialPositions(nodeIds).map((p) => ({ ...p }));
    const idx = new Map(pts.map((p, i) => [p.id, i]));
    const links = normEdges
      .map((e) => ({ a: idx.get(e.from), b: idx.get(e.to) }))
      .filter((x) => x.a != null && x.b != null) as Array<{ a: number; b: number }>;

    for (let iter = 0; iter < 90; iter++) {
      // Repel
      for (let i = 0; i < pts.length; i++) {
        for (let j = i + 1; j < pts.length; j++) {
          const dx = pts[i].x - pts[j].x;
          const dy = pts[i].y - pts[j].y;
          const d2 = dx * dx + dy * dy + 0.001;
          const f = 0.018 / d2;
          pts[i].x += dx * f;
          pts[i].y += dy * f;
          pts[j].x -= dx * f;
          pts[j].y -= dy * f;
        }
      }
      // Attract along edges
      for (const l of links) {
        const a = pts[l.a];
        const b = pts[l.b];
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const f = 0.0022;
        a.x += dx * f;
        a.y += dy * f;
        b.x -= dx * f;
        b.y -= dy * f;
      }
      // Clamp
      for (const p of pts) {
        p.x = Math.max(6, Math.min(94, p.x));
        p.y = Math.max(8, Math.min(92, p.y));
      }
    }

    return pts;
  }, [nodeIds, normEdges]);

  const posById = useMemo(() => new Map(placed.map((p) => [p.id, p])), [placed]);

  const visibleNodeIdSet = useMemo(() => {
    const set = new Set<string>();
    for (const id of nodeIds) {
      const n = nodeById.get(id);
      const st = asString((n as any)?.status);
      const k = statusKind(st);
      const score = activityScoreByNode.get(id) ?? 0;
      if (filter === "all") set.add(id);
      else if (filter === "active" && k === "ok") set.add(id);
      else if (filter === "degraded" && k === "bad") set.add(id);
      else if (filter === "recent" && score > 0.35) set.add(id);
    }
    // Always keep the selected node visible.
    if (selectedNodeId) set.add(selectedNodeId);
    return set;
  }, [activityScoreByNode, filter, nodeById, nodeIds, selectedNodeId]);

  const visibleEdges = useMemo(() => {
    return normEdges.filter((e) => visibleNodeIdSet.has(e.from) && visibleNodeIdSet.has(e.to));
  }, [normEdges, visibleNodeIdSet]);

  const counts = useMemo(() => {
    let active = 0;
    let degraded = 0;
    let recent = 0;
    for (const id of nodeIds) {
      const n = nodeById.get(id);
      const st = asString((n as any)?.status);
      const k = statusKind(st);
      if (k === "ok") active++;
      if (k === "bad") degraded++;
      if ((activityScoreByNode.get(id) ?? 0) > 0.35) recent++;
    }
    return { active, degraded, recent, total: nodeIds.length };
  }, [activityScoreByNode, nodeById, nodeIds]);

  useEffect(() => {
    function onLeave() {
      setHoverId(null);
      setTooltip(null);
    }
    const el = wrapRef.current;
    if (!el) return;
    el.addEventListener("mouseleave", onLeave);
    return () => el.removeEventListener("mouseleave", onLeave);
  }, []);

  return (
    <div ref={wrapRef} className="relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="absolute inset-0 nexus-opsmesh-bg" aria-hidden="true" />

      <div className="relative px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Topology</div>
            <div className="mt-0.5 text-sm text-muted-foreground">
              Nodes <span className="text-foreground">{nodeIds.length}</span>
              {selectedNodeId ? (
                <>
                  <span className="mx-2 text-muted-foreground/40">•</span>
                  selected <span className="font-mono text-foreground">{selectedNodeId}</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-muted-foreground">
            <button
              type="button"
              onClick={() => setFilter("all")}
              className={`rounded-md border px-2 py-1 ${filter === "all" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/40"}`}
            >
              All <span className="font-mono opacity-80">{counts.total}</span>
            </button>
            <button
              type="button"
              onClick={() => setFilter("active")}
              className={`rounded-md border px-2 py-1 ${filter === "active" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/40"}`}
            >
              Active <span className="font-mono opacity-80">{counts.active}</span>
            </button>
            <button
              type="button"
              onClick={() => setFilter("degraded")}
              className={`rounded-md border px-2 py-1 ${filter === "degraded" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/40"}`}
            >
              Degraded <span className="font-mono opacity-80">{counts.degraded}</span>
            </button>
            <button
              type="button"
              onClick={() => setFilter("recent")}
              className={`rounded-md border px-2 py-1 ${filter === "recent" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/40"}`}
              title="Nodes with recent trace activity"
            >
              Recent <span className="font-mono opacity-80">{counts.recent}</span>
            </button>
          </div>
        </div>
      </div>

      <div className="relative px-3 pb-3">
        <svg className="h-[220px] w-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <linearGradient id="opsEdge" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.32)" />
              <stop offset="100%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.14)" />
            </linearGradient>
            <marker id="opsArrow" markerWidth="6" markerHeight="6" refX="5.4" refY="3" orient="auto" markerUnits="strokeWidth">
              <path d="M0,0 L6,3 L0,6 z" fill="rgba(var(--nexus-stars-accent-rgb), 0.45)" />
            </marker>
          </defs>

          <g>
            {visibleEdges.slice(0, 420).map((e, i) => {
              const a = posById.get(e.from);
              const b = posById.get(e.to);
              if (!a || !b) return null;
              const hot = (activityScoreByNode.get(e.from) ?? 0) > 0.45 || (activityScoreByNode.get(e.to) ?? 0) > 0.45;
              const cls = hot ? "nexus-opsmesh-edge nexus-opsmesh-edge-hot" : "nexus-opsmesh-edge";
              return (
                <line
                  key={`${e.from}:${e.to}:${i}`}
                  x1={a.x}
                  y1={a.y}
                  x2={b.x}
                  y2={b.y}
                  className={cls}
                  stroke="url(#opsEdge)"
                  strokeWidth="0.28"
                  markerEnd="url(#opsArrow)"
                  vectorEffect="non-scaling-stroke"
                />
              );
            })}
          </g>

          <g>
            {placed.filter((p) => visibleNodeIdSet.has(p.id)).map((p) => {
              const n = nodeById.get(p.id);
              const st = asString((n as any)?.status);
              const k = statusKind(st);
              const focused = selectedNodeId === p.id;
              const hovered = hoverId === p.id;
              const score = activityScoreByNode.get(p.id) ?? 0;
              const r = 1.3 + score * 2.4 + (focused ? 0.9 : 0) + (hovered ? 0.5 : 0);
              const fill =
                k === "bad"
                  ? "rgba(var(--nexus-stars-bad-rgb), 0.95)"
                  : k === "ok"
                    ? "rgba(var(--nexus-stars-accent-rgb), 0.95)"
                    : k === "done"
                      ? "rgba(99,102,241,0.90)"
                      : "rgba(var(--nexus-stars-dust-rgb), 0.70)";
              const halo =
                k === "bad"
                  ? "rgba(var(--nexus-stars-bad-rgb), 0.10)"
                  : "rgba(var(--nexus-stars-accent-rgb), 0.08)";

              return (
                <g
                  key={p.id}
                  onMouseMove={(ev) => {
                    const box = wrapRef.current?.getBoundingClientRect();
                    if (!box) return;
                    setHoverId(p.id);
                    setTooltip({ x: ev.clientX - box.left, y: ev.clientY - box.top });
                  }}
                  onMouseLeave={() => {
                    setHoverId((cur) => (cur === p.id ? null : cur));
                    setTooltip(null);
                  }}
                  onClick={() => onSelectNodeId(focused ? null : p.id)}
                  style={{ cursor: "pointer" }}
                >
                  {(focused || hovered || score > 0.5 || k === "bad") && (
                    <circle cx={p.x} cy={p.y} r={r * 2.8} fill={halo} className="nexus-opsmesh-pulse" />
                  )}
                  <circle cx={p.x} cy={p.y} r={r} fill={fill} />
                  {(focused || hovered || score > 0.65) && (
                    <text
                      x={p.x}
                      y={p.y - (r * 2.7 + 0.6)}
                      textAnchor="middle"
                      fontSize="2.3"
                      fill="rgba(var(--foreground), 0.70)"
                    >
                      {asString((n as any)?.label) || p.id}
                    </text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {hoverId && tooltip ? (
          <div
            className="pointer-events-none absolute z-10 w-[280px] -translate-y-2 rounded-lg border border-border bg-popover px-3 py-2 text-xs shadow-lg"
            style={{
              left: Math.min(tooltip.x + 10, (wrapRef.current?.clientWidth ?? 0) - 300),
              top: Math.max(tooltip.y - 8, 8),
            }}
          >
            {(() => {
              const n = nodeById.get(hoverId);
              const st = asString((n as any)?.status) || "—";
              const label = asString((n as any)?.label) || hoverId;
              const actor = asString((n as any)?.actor);
              const summary = asString((n as any)?.summary);
              const last = lastTraceByNode.get(hoverId) ?? null;
              const age = last == null ? null : Math.max(0, Date.now() / 1000 - last);
              return (
                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="truncate font-medium text-foreground">{label}</div>
                      <div className="truncate font-mono text-[11px] text-muted-foreground">{hoverId}</div>
                    </div>
                    <div className="shrink-0 rounded-md border border-border bg-muted/40 px-2 py-0.5 text-[10px] text-muted-foreground">
                      {st}
                    </div>
                  </div>
                  <div className="text-muted-foreground">
                    {actor ? (
                      <>
                        <span className="text-muted-foreground">actor</span>{" "}
                        <span className="font-mono text-foreground/90">{actor}</span>
                      </>
                    ) : (
                      "—"
                    )}
                    <span className="mx-2 text-muted-foreground/40">•</span>
                    <span className="text-muted-foreground">last event</span>{" "}
                    <span className="font-mono text-foreground/90">{prettyAge(age)}</span>
                  </div>
                  {summary ? <div className="line-clamp-3 text-muted-foreground">{summary}</div> : null}
                </div>
              );
            })()}
          </div>
        ) : null}
      </div>
    </div>
  );
}

