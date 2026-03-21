"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { TopologyEdge, TopologyNode } from "@/types/nexus-payload";

/** Canvas ring field + Framer orbital layout (legacy standalone hub removed; this is the canonical hub). */
const BASE_SIZE = 520;
const BASE_RADIUS = [55, 120, 190, 265, 335] as const;
const DOTS_PER_RING = [24, 36, 48, 60, 72] as const;

type Pt = { x: number; y: number };

function parseNodeOrder(id: string): number {
  const m = id.match(/\d+/);
  return m ? parseInt(m[0], 10) : 0;
}

/** Orbit order: topological walk when edges exist, else numeric id order */
function orderedNodes(nodes: TopologyNode[], edges: TopologyEdge[]): TopologyNode[] {
  if (nodes.length === 0) return [];
  const ids = new Set(nodes.map((n) => n.id));
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const incoming = new Map<string, number>();
  ids.forEach((id) => incoming.set(id, 0));
  edges.forEach((e) => {
    if (ids.has(e.from) && ids.has(e.to)) incoming.set(e.to, (incoming.get(e.to) ?? 0) + 1);
  });
  const adj = new Map<string, string[]>();
  edges.forEach((e) => {
    if (ids.has(e.from) && ids.has(e.to)) {
      if (!adj.has(e.from)) adj.set(e.from, []);
      adj.get(e.from)!.push(e.to);
    }
  });
  const queue = Array.from(ids).filter((id) => (incoming.get(id) ?? 0) === 0);
  queue.sort((a, b) => parseNodeOrder(a) - parseNodeOrder(b));
  const out: TopologyNode[] = [];
  const seen = new Set<string>();
  const incCopy = new Map(incoming);
  const q = [...queue];
  while (q.length) {
    const id = q.shift()!;
    if (seen.has(id)) continue;
    seen.add(id);
    const n = byId.get(id);
    if (n) out.push(n);
    for (const next of adj.get(id) ?? []) {
      const v = (incCopy.get(next) ?? 0) - 1;
      incCopy.set(next, v);
      if (v === 0) q.push(next);
    }
  }
  for (const n of nodes) {
    if (!seen.has(n.id)) out.push(n);
  }
  return out;
}

/** Evenly space agents on one orbit; coords are % of container (center 50,50) */
function orbitPositions(nodes: TopologyNode[], edges: TopologyEdge[]): Array<{ node: TopologyNode; pos: Pt }> {
  const list = orderedNodes(nodes, edges);
  const n = list.length;
  const r = 34;
  return list.map((node, i) => {
    const angle = (i / Math.max(n, 1)) * Math.PI * 2 - Math.PI / 2;
    return {
      node,
      pos: {
        x: 50 + Math.cos(angle) * r,
        y: 50 + Math.sin(angle) * r,
      },
    };
  });
}

function AmbientRingsCanvas({ width, height }: { width: number; height: number }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const size = Math.max(0, Math.min(width, height));
  const rs = useMemo(() => BASE_RADIUS.map((r) => (r * size) / BASE_SIZE), [size]);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas || size <= 0) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = Math.min(2, typeof window !== "undefined" ? window.devicePixelRatio : 1);
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    canvas.style.width = `${width}px`;
    canvas.style.height = `${height}px`;
    ctx.scale(dpr, dpr);

    const cx = width / 2;
    const cy = height / 2;

    ctx.clearRect(0, 0, width, height);

    for (let ring = 0; ring < BASE_RADIUS.length; ring++) {
      const count = DOTS_PER_RING[ring];
      const rad = rs[ring];
      for (let i = 0; i < count; i++) {
        const a = (i / count) * Math.PI * 2;
        const x = cx + Math.cos(a) * rad;
        const y = cy + Math.sin(a) * rad;
        const dot = 1.1 + ring * 0.1;
        const alpha = 0.42 + ring * 0.03;
        ctx.beginPath();
        ctx.arc(x, y, dot, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(34, 211, 238, ${alpha})`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x, y, dot * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${alpha * 0.55})`;
        ctx.fill();
      }
    }

    ctx.strokeStyle = "rgba(34, 211, 238, 0.12)";
    ctx.lineWidth = 1;
    for (let ring = 0; ring < BASE_RADIUS.length; ring++) {
      ctx.beginPath();
      ctx.arc(cx, cy, rs[ring], 0, Math.PI * 2);
      ctx.stroke();
    }
  }, [width, height, size, rs]);

  return <canvas ref={ref} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden />;
}

const CENTER_PCT: Pt = { x: 50, y: 50 };

function CentralStar() {
  return (
    <div className="relative flex items-center justify-center">
      <motion.div
        animate={{ scale: [1, 1.2, 1], opacity: [0.5, 0.8, 0.5] }}
        transition={{ duration: 4, repeat: Infinity }}
        className="absolute h-28 w-28 rounded-full bg-cyan-500/20 blur-3xl sm:h-32 sm:w-32"
      />
      <div className="relative z-20 h-10 w-10 rounded-full bg-white shadow-[0_0_50px_20px_rgba(34,211,238,0.8)] sm:h-12 sm:w-12">
        <div className="absolute inset-0 rounded-full bg-cyan-400 opacity-20 animate-ping" />
      </div>
    </div>
  );
}

function AgentStar({
  label,
  selected,
  pipelineActive,
  position,
}: {
  label: string;
  /** User focus from topology / stream filter */
  selected: boolean;
  /** Pipeline “currently running” agent */
  pipelineActive: boolean;
  position: Pt;
}) {
  const dotClass = pipelineActive
    ? "scale-125 bg-[var(--nexus-glow)] shadow-[0_0_14px_6px_rgba(0,212,170,0.5)]"
    : selected
      ? "scale-110 bg-[var(--nexus-glow)] shadow-[0_0_0_2px_rgba(0,212,170,0.28),0_0_12px_4px_rgba(0,212,170,0.45)]"
      : "scale-100 bg-slate-600 shadow-none";
  const labelClass = pipelineActive
    ? "text-[var(--nexus-glow)]"
    : selected
      ? "text-[var(--nexus-glow)] font-semibold"
      : "text-slate-500";
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      style={{ left: `${position.x}%`, top: `${position.y}%` }}
      className="absolute z-20 flex flex-col items-center gap-2 -translate-x-1/2 -translate-y-1/2"
    >
      <div className={`h-3 w-3 rounded-full transition-all duration-500 ${dotClass}`} />
      <span className={`max-w-[140px] text-center font-mono text-[9px] uppercase tracking-widest ${labelClass}`}>
        {label}
      </span>
    </motion.div>
  );
}

function StarParticle({ start, end }: { start: Pt; end: Pt }) {
  return (
    <motion.div
      initial={{ left: `${start.x}%`, top: `${start.y}%`, opacity: 1, scale: 0.5 }}
      animate={{ left: `${end.x}%`, top: `${end.y}%`, opacity: 0, scale: 1.2 }}
      transition={{ duration: 1.5, ease: "easeOut" }}
      className="pointer-events-none absolute z-10 h-1 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white shadow-[0_0_8px_2px_rgba(255,255,255,0.6)]"
    />
  );
}

interface NexusStarSystemProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  activeNodeId: string | null;
  signalCount?: number;
}

export function NexusStarSystem({
  nodes,
  edges,
  activeNodeId,
  signalCount = 0,
}: NexusStarSystemProps) {
  const edgeGradId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const prevSignalRef = useRef(0);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [particles, setParticles] = useState<Array<{ id: string; end: Pt }>>([]);
  /** Avoid hydration mismatch: server vs client time/locale differ for `toLocaleTimeString()`. */
  const [clock, setClock] = useState("--:--:--");

  const placed = useMemo(() => orbitPositions(nodes, edges), [nodes, edges]);

  const pipelineActiveId = placed.find((p) => p.node.status === "ACTIVE")?.node.id ?? null;
  const resolvedFocusId = activeNodeId ?? pipelineActiveId;

  const activePos = useMemo(() => {
    const hit = placed.find((p) => p.node.id === resolvedFocusId);
    return hit?.pos ?? null;
  }, [placed, resolvedFocusId]);

  useEffect(() => {
    const fmt = () =>
      new Date().toLocaleTimeString("en-GB", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    setClock(fmt());
    const id = setInterval(() => setClock(fmt()), 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => {
      const r = el.getBoundingClientRect();
      setBox({ w: Math.floor(r.width), h: Math.floor(r.height) });
    });
    ro.observe(el);
    const r = el.getBoundingClientRect();
    setBox({ w: Math.floor(r.width), h: Math.floor(r.height) });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (!activePos || signalCount <= prevSignalRef.current) return;
    prevSignalRef.current = signalCount;
    const burst = 4;
    const next: Array<{ id: string; end: Pt }> = [];
    for (let i = 0; i < burst; i++) {
      next.push({
        id: `${signalCount}-${i}-${Date.now()}`,
        end: {
          x: activePos.x + (Math.random() - 0.5) * 3,
          y: activePos.y + (Math.random() - 0.5) * 3,
        },
      });
    }
    setParticles((prev) => [...prev, ...next]);
    const t = window.setTimeout(() => {
      setParticles((prev) => prev.filter((p) => !next.some((n) => n.id === p.id)));
    }, 1600);
    return () => clearTimeout(t);
  }, [signalCount, activePos]);

  return (
    <div
      ref={containerRef}
      className="relative h-full min-h-[min(480px,70vh)] w-full overflow-hidden rounded-3xl border border-[color:var(--nexus-hub-frame)] bg-[var(--nexus-bg)] shadow-inner"
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_40%,rgba(34,211,238,0.08),transparent_55%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.035)_1px,transparent_1px)] bg-[length:24px_24px]" />
      <div className="absolute inset-0 opacity-[0.12] mix-blend-overlay bg-[radial-gradient(circle_at_20%_30%,rgba(255,255,255,0.15),transparent_50%)]" />

      {box.w > 0 && box.h > 0 && <AmbientRingsCanvas width={box.w} height={box.h} />}

      <svg
        className="pointer-events-none absolute inset-0 z-[5] h-full w-full"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id={edgeGradId} x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="rgba(34, 211, 238, 0.25)" />
            <stop offset="100%" stopColor="rgba(34, 211, 238, 0.08)" />
          </linearGradient>
        </defs>
        {edges.map((e, i) => {
          const a = placed.find((p) => p.node.id === e.from)?.pos;
          const b = placed.find((p) => p.node.id === e.to)?.pos;
          if (!a || !b) return null;
          return (
            <line
              key={`${e.from}-${e.to}-${i}`}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={`url(#${edgeGradId})`}
              strokeWidth={0.15}
              vectorEffect="non-scaling-stroke"
            />
          );
        })}
      </svg>

      <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2">
        <CentralStar />
      </div>

      {placed.map(({ node, pos }) => (
        <AgentStar
          key={node.id}
          label={node.label}
          selected={activeNodeId != null && node.id === activeNodeId}
          pipelineActive={node.status === "ACTIVE"}
          position={pos}
        />
      ))}

      <AnimatePresence>
        {particles.map((p) => (
          <StarParticle key={p.id} start={CENTER_PCT} end={p.end} />
        ))}
      </AnimatePresence>

      <div className="absolute bottom-6 left-6 z-20 font-mono text-[10px] text-cyan-500/50">
        SYSTEM_CLOCK: {clock}
        <br />
        MESH_SYNC: STABLE // ENTROPY: 0.031
      </div>
    </div>
  );
}
