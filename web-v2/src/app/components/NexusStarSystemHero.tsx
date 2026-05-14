import { useMemo } from "react";

type NodeLike = { id?: unknown; label?: unknown; status?: unknown };
type EdgeLike = { from?: unknown; to?: unknown; source?: unknown; target?: unknown };

function asString(v: unknown) {
  return typeof v === "string" ? v : v === null || v === undefined ? "" : String(v);
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

function statusTone(status: string) {
  const s = (status || "").toUpperCase();
  if (s === "ACTIVE" || s === "RUNNING" || s === "OK") return "active";
  if (s === "FAILED" || s === "ERROR") return "bad";
  if (s === "COMPLETED") return "done";
  return "idle";
}

function hash01(s: string) {
  // Small deterministic hash -> [0,1)
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  // Unsigned -> [0, 2^32)
  const u = h >>> 0;
  return (u % 1_000_000) / 1_000_000;
}

function placedPositions(ids: string[]) {
  // Constellation layout: stable pseudo-random positions (no orbit rings).
  const margin = 10; // keep away from edges
  return ids.map((id) => {
    const a = hash01(`${id}:a`);
    const b = hash01(`${id}:b`);
    const x = margin + a * (100 - margin * 2);
    const y = margin + b * (100 - margin * 2);
    return { id, x, y };
  });
}

export function NexusStarSystemHero({
  nodes,
  edges,
  activeNodeId,
}: {
  nodes: Array<Record<string, unknown>>;
  edges: Array<Record<string, unknown>>;
  activeNodeId: string | null;
}) {
  const nodeIds = useMemo(() => {
    const ids = (nodes as NodeLike[])
      .map((n) => asString((n as any)?.id))
      .filter(Boolean);
    // Stable order (avoid shuffling every refresh)
    return ids.slice().sort();
  }, [nodes]);

  const nodeById = useMemo(() => {
    const m = new Map<string, NodeLike>();
    for (const n of nodes as NodeLike[]) {
      const id = asString((n as any)?.id);
      if (!id) continue;
      m.set(id, n);
    }
    return m;
  }, [nodes]);

  const placed = useMemo(() => placedPositions(nodeIds), [nodeIds]);
  const posById = useMemo(() => new Map(placed.map((p) => [p.id, p])), [placed]);
  const normEdges = useMemo(() => normalizeEdges(edges), [edges]);

  const counts = useMemo(() => {
    let active = 0;
    let bad = 0;
    for (const id of nodeIds) {
      const st = asString((nodeById.get(id) as any)?.status);
      const tone = statusTone(st);
      if (tone === "active") active++;
      if (tone === "bad") bad++;
    }
    return { total: nodeIds.length, active, bad };
  }, [nodeById, nodeIds]);

  return (
    <div className="nexus-star-hero relative overflow-hidden rounded-xl border border-border bg-card">
      <div className="relative z-10 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Topology</div>
            <div className="mt-0.5 text-sm text-muted-foreground">
              Nodes <span className="text-foreground">{counts.total}</span>
              {counts.active ? (
                <>
                  <span className="mx-2 text-muted-foreground/40">•</span>
                  active <span className="text-foreground">{counts.active}</span>
                </>
              ) : null}
              {counts.bad ? (
                <>
                  <span className="mx-2 text-muted-foreground/40">•</span>
                  degraded <span className="text-foreground">{counts.bad}</span>
                </>
              ) : null}
            </div>
          </div>
          <div className="text-[11px] text-muted-foreground">
            {activeNodeId ? (
              <>
                focus <span className="font-mono text-foreground">{activeNodeId}</span>
              </>
            ) : (
              "mesh overview"
            )}
          </div>
        </div>
      </div>

      <svg
        className="pointer-events-none absolute inset-0 z-0 h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="nsh-edge" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.22)" />
            <stop offset="100%" stopColor="rgba(var(--nexus-stars-accent-rgb), 0.06)" />
          </linearGradient>
        </defs>

        {/* Edges */}
        <g>
          {normEdges.slice(0, 240).map((e, i) => {
            const a = posById.get(e.from);
            const b = posById.get(e.to);
            if (!a || !b) return null;
            return (
              <line
                key={`${e.from}:${e.to}:${i}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke="url(#nsh-edge)"
                strokeWidth="0.18"
                vectorEffect="non-scaling-stroke"
                opacity="0.85"
              />
            );
          })}
        </g>

        {/* Nodes */}
        <g>
          {placed.map((p) => {
            const n = nodeById.get(p.id);
            const st = asString((n as any)?.status);
            const tone = statusTone(st);
            const focused = Boolean(activeNodeId && p.id === activeNodeId);
            const active = tone === "active";
            const bad = tone === "bad";
            const fill = bad
              ? "rgba(var(--nexus-stars-bad-rgb), 0.95)"
              : active || focused
                ? "rgba(var(--nexus-stars-accent-rgb), 0.95)"
                : "rgba(var(--nexus-stars-dust-rgb), 0.85)";
            const r = focused ? 1.55 : active ? 1.25 : 1.0;
            return (
              <g key={p.id}>
                {(focused || active || bad) && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r={r * 3.2}
                    fill={bad ? "rgba(var(--nexus-stars-bad-rgb), 0.10)" : "rgba(var(--nexus-stars-accent-rgb), 0.10)"}
                    className="nexus-star-hero-pulse"
                  />
                )}
                <circle cx={p.x} cy={p.y} r={r} fill={fill} />
              </g>
            );
          })}
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-0 z-0 nexus-star-hero-grain" aria-hidden="true" />
    </div>
  );
}

