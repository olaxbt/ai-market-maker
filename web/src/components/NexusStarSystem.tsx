"use client";

import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from "framer-motion";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import type { TopologyEdge, TopologyNode } from "@/types/nexus-payload";

/** Rotating 3D-like sphere field + Framer orbital layout for the canonical hub. */

type Pt = { x: number; y: number };
type Dot3D = {
  id: number;
  x: number;
  y: number;
  z: number;
  twinklePhase: number;
  twinkleRate: number;
  twinkleAmp: number;
  baseSize: number;
  spike: number;
  bright: boolean;
};

const BASE_SIZE = 520;
const BASE_RADIUS = [55, 120, 190, 265, 335] as const;
const DOTS_PER_RING = [24, 36, 48, 60, 72] as const;
const INTRO_MS = 2000;
const BURST_MS = 1300;

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
function orbitPositions(
  nodes: TopologyNode[],
  edges: TopologyEdge[],
): Array<{ node: TopologyNode; pos: Pt }> {
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

  return (
    <canvas ref={ref} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden />
  );
}

function buildSphereDots(count: number): Dot3D[] {
  // Fibonacci sphere gives an even "constellation" spread.
  const phi = Math.PI * (3 - Math.sqrt(5));
  const dots: Dot3D[] = [];
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(1, count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = phi * i;
    dots.push({
      id: i,
      x: Math.cos(theta) * radius,
      y,
      z: Math.sin(theta) * radius,
      twinklePhase: Math.random() * Math.PI * 2,
      twinkleRate: 0.55 + Math.random() * 1.15,
      twinkleAmp: 0.18 + Math.random() * 0.42,
      baseSize: 0.45 + Math.random() * 1.9,
      spike: 0.6 + Math.random() * 1.5,
      bright: Math.random() < 0.08,
    });
  }
  return dots;
}

function RotatingSphereCanvas({
  width,
  height,
  mode,
  burstStartedAt,
}: {
  width: number;
  height: number;
  mode: "intro" | "burst";
  burstStartedAt: number | null;
}) {
  const ref = useRef<HTMLCanvasElement>(null);
  const size = Math.max(0, Math.min(width, height));
  const dots = useMemo(() => buildSphereDots(360), []);

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
    // Denser and smaller sphere silhouette in center.
    const radius = size * 0.25;
    const perspective = size * 1.35;
    let raf = 0;

    const draw = (tMs: number) => {
      const t = tMs * 0.001;
      ctx.clearRect(0, 0, width, height);

      const spinY = t * 0.18;
      const spinX = Math.sin(t * 0.13) * 0.14;
      const cosY = Math.cos(spinY);
      const sinY = Math.sin(spinY);
      const cosX = Math.cos(spinX);
      const sinX = Math.sin(spinX);
      const burstT =
        mode === "burst" && burstStartedAt != null
          ? Math.max(0, Math.min(1, (performance.now() - burstStartedAt) / BURST_MS))
          : 0;
      const burstSpread = 1 + burstT * 6.4;
      const burstFade = 1 - burstT;

      const projected = dots
        .map((p) => {
          // Rotate around Y then X.
          const x1 = p.x * cosY + p.z * sinY;
          const z1 = p.z * cosY - p.x * sinY;
          const y2 = p.y * cosX - z1 * sinX;
          const z2 = z1 * cosX + p.y * sinX;
          const depth = (z2 + 1) * 0.5;
          const scale = perspective / (perspective - z2 * radius);
          const x = cx + x1 * radius * scale * burstSpread;
          const y = cy + y2 * radius * scale * burstSpread;
          return { x, y, depth, scale, dot: p };
        })
        .sort((a, b) => a.depth - b.depth);

      // Option B: dynamic triangulation-style mesh (clean futuristic net).
      const meshNodes = projected
        .filter((p) => p.depth > 0.12)
        .sort((a, b) => b.depth - a.depth)
        .slice(0, 110);
      const byId = new Map(meshNodes.map((n) => [n.dot.id, n]));
      const edgeSet = new Set<string>();
      const triSet = new Set<string>();
      const edgeKey = (a: number, b: number) => (a < b ? `${a}-${b}` : `${b}-${a}`);
      const triKey = (a: number, b: number, c: number) => [a, b, c].sort((x, y) => x - y).join("-");

      for (const a of meshNodes) {
        const neighbors = meshNodes
          .filter((b) => b.dot.id !== a.dot.id)
          .map((b) => {
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            return { b, d: Math.hypot(dx, dy) };
          })
          .filter((x) => x.d < size * 0.2)
          .sort((x, y) => x.d - y.d)
          .slice(0, 3)
          .map((x) => x.b);

        for (let i = 0; i < neighbors.length; i++) {
          for (let j = i + 1; j < neighbors.length; j++) {
            const b = neighbors[i];
            const c = neighbors[j];
            if (!b || !c) continue;
            const bcDx = b.x - c.x;
            const bcDy = b.y - c.y;
            const bc = Math.hypot(bcDx, bcDy);
            if (bc > size * 0.2) continue;
            triSet.add(triKey(a.dot.id, b.dot.id, c.dot.id));
            edgeSet.add(edgeKey(a.dot.id, b.dot.id));
            edgeSet.add(edgeKey(a.dot.id, c.dot.id));
            edgeSet.add(edgeKey(b.dot.id, c.dot.id));
          }
        }
      }

      // Triangle edges with subtle animated shimmer.
      Array.from(edgeSet).forEach((key) => {
        const [ia, ib] = key.split("-").map((x) => Number.parseInt(x, 10));
        const a = byId.get(ia);
        const b = byId.get(ib);
        if (!a || !b) return;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.hypot(dx, dy);
        const depth = (a.depth + b.depth) * 0.5;
        const shimmer = 0.5 + 0.5 * Math.sin(t * 1.4 + (ia + ib) * 0.013);
        const alpha =
          Math.max(0.02, 0.16 - dist / (size * 2.7)) * (0.45 + depth * 0.55) * shimmer * burstFade;
        ctx.strokeStyle = `rgba(96, 231, 255, ${alpha})`;
        ctx.lineWidth = 0.48;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      });

      for (const p of projected) {
        const glow = 0.33 + p.depth * 0.63;
        const pulse =
          1 -
          p.dot.twinkleAmp +
          Math.sin(t * p.dot.twinkleRate + p.dot.twinklePhase) * p.dot.twinkleAmp;
        const alpha = Math.max(0, glow * pulse * burstFade);
        const r = Math.max(0.5, p.dot.baseSize * (0.65 + p.depth * 1.05));

        const tint = p.dot.bright
          ? "rgba(205, 225, 255,"
          : p.depth > 0.66
            ? "rgba(198, 255, 250,"
            : "rgba(150, 238, 255,";

        // 1) Soft atmospheric halo around the star.
        const haloR = r * (p.dot.bright ? 5.4 : 3.1);
        const halo = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, haloR);
        halo.addColorStop(0, `${tint}${Math.min(0.45, alpha * 0.55)})`);
        halo.addColorStop(0.55, `${tint}${Math.min(0.16, alpha * 0.2)})`);
        halo.addColorStop(1, `${tint}0)`);
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(p.x, p.y, haloR, 0, Math.PI * 2);
        ctx.fill();

        // 2) Bright core.
        ctx.beginPath();
        ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
        ctx.fillStyle = `${tint}${Math.min(1, alpha)})`;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(p.x, p.y, r * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${Math.min(0.92, alpha * 0.82)})`;
        ctx.fill();

        // 3) Strict 4-point cross flare (no diagonals).
        const spike = p.dot.spike * (p.dot.bright ? 3.4 : 1.2) * (0.65 + p.depth * 1.05);
        const spikeAlpha = alpha * (p.dot.bright ? 0.95 : 0.62);
        ctx.strokeStyle = `rgba(220, 240, 255, ${spikeAlpha})`;
        ctx.lineWidth = Math.max(0.25, r * (p.dot.bright ? 0.32 : 0.2));
        ctx.beginPath();
        ctx.moveTo(p.x - spike, p.y);
        ctx.lineTo(p.x + spike, p.y);
        ctx.moveTo(p.x, p.y - spike);
        ctx.lineTo(p.x, p.y + spike);
        ctx.stroke();
      }
      raf = requestAnimationFrame(draw);
    };

    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [width, height, size, dots, mode, burstStartedAt]);

  return (
    <canvas ref={ref} className="pointer-events-none absolute inset-0 h-full w-full" aria-hidden />
  );
}

const CENTER_PCT: Pt = { x: 50, y: 50 };

function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x));
}

function CentralStar({ energy, variant }: { energy: number; variant: "hub" | "loading" }) {
  if (variant === "loading") {
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

  const e = clamp01(energy);
  const glow = 0.22 + e * 0.55;
  const pulseDur = 6 - e * 3.2; // energetic = faster
  return (
    <div className="relative flex items-center justify-center">
      <motion.div
        animate={{
          scale: [1, 1.22, 1],
          opacity: [0.28 + e * 0.12, 0.62 + e * 0.2, 0.28 + e * 0.12],
        }}
        transition={{ duration: pulseDur, repeat: Infinity, ease: "easeInOut" }}
        className="absolute h-32 w-32 rounded-full bg-cyan-500/20 blur-3xl sm:h-40 sm:w-40"
      />

      {/* Rotating aura ring */}
      <motion.div
        className="absolute z-10 h-40 w-40 rounded-full nexus-core-aura sm:h-48 sm:w-48"
        animate={{ rotate: 360 }}
        transition={{ duration: 22 - e * 10, repeat: Infinity, ease: "linear" }}
        aria-hidden
      />

      {/* Thin orbital wireframe ring */}
      <motion.div
        className="absolute z-10 h-44 w-44 rounded-full border border-cyan-200/10 sm:h-52 sm:w-52"
        animate={{ rotate: -360 }}
        transition={{ duration: 36 - e * 14, repeat: Infinity, ease: "linear" }}
        style={{
          boxShadow: `0 0 ${24 + e * 22}px rgba(34,211,238,${0.08 + e * 0.12})`,
        }}
        aria-hidden
      />

      <div
        className="relative z-20 h-11 w-11 rounded-full bg-white sm:h-14 sm:w-14"
        style={{
          boxShadow: `0 0 50px 20px rgba(34,211,238,${0.55 + e * 0.35})`,
        }}
      >
        <div
          className="absolute inset-0 rounded-full bg-cyan-300/30 nexus-core-star-nucleus"
          style={{ opacity: 0.18 + e * 0.18 }}
        />
        <div
          className="absolute -inset-2 rounded-full border border-cyan-200/10"
          style={{ boxShadow: `0 0 22px rgba(34,211,238,${glow})` }}
          aria-hidden
        />
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
      <span
        className={`max-w-[140px] text-center font-mono text-[9px] uppercase tracking-widest ${labelClass}`}
      >
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
  readyToReveal: boolean;
  onIntroDone?: () => void;
  /** Called when the burst/explode phase starts (useful for syncing global reveal). */
  onBurstStart?: () => void;
  playIntro?: boolean;
  /** When true, remove the framed "card" look (used for full-screen loading). */
  frameless?: boolean;
}

export function NexusStarSystem({
  nodes,
  edges,
  activeNodeId,
  signalCount = 0,
  readyToReveal,
  onIntroDone,
  onBurstStart,
  playIntro = true,
  frameless = false,
}: NexusStarSystemProps) {
  const edgeGradId = useId().replace(/:/g, "");
  const containerRef = useRef<HTMLDivElement>(null);
  const prevSignalRef = useRef(0);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const [particles, setParticles] = useState<Array<{ id: string; end: Pt }>>([]);
  const [hubPhase, setHubPhase] = useState<"intro" | "burst" | "done">(
    playIntro ? "intro" : "done",
  );
  const burstStartedAtRef = useRef<number | null>(null);
  /** Avoid hydration mismatch: server vs client time/locale differ for `toLocaleTimeString()`. */
  const [clock, setClock] = useState("--:--:--");
  const [energy, setEnergy] = useState(0.22);
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);
  const tiltXS = useSpring(tiltX, { stiffness: 120, damping: 24, mass: 0.35 });
  const tiltYS = useSpring(tiltY, { stiffness: 120, damping: 24, mass: 0.35 });
  const energyMV = useMotionValue(energy);
  useEffect(() => {
    energyMV.set(energy);
  }, [energy, energyMV]);

  const rotateX = useTransform([tiltYS, energyMV], (v: number[]) => {
    const y = v[0] ?? 0;
    const e = v[1] ?? 0;
    return (-y * (2.2 + e * 1.2)).toFixed(2);
  });
  const rotateY = useTransform([tiltXS, energyMV], (v: number[]) => {
    const x = v[0] ?? 0;
    const e = v[1] ?? 0;
    return (x * (2.6 + e * 1.3)).toFixed(2);
  });
  const scale = useTransform(energyMV, (e) => 1 + e * 0.01);

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

  // Subtle micro-parallax tilt based on pointer position.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    // Disable parallax on the frameless loader.
    if (frameless) return;
    const onMove = (e: MouseEvent) => {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / Math.max(1, r.width);
      const py = (e.clientY - r.top) / Math.max(1, r.height);
      const nx = (px - 0.5) * 2;
      const ny = (py - 0.5) * 2;
      tiltX.set(nx);
      tiltY.set(ny);
    };
    const onLeave = () => {
      tiltX.set(0);
      tiltY.set(0);
    };
    el.addEventListener("mousemove", onMove, { passive: true });
    el.addEventListener("mouseleave", onLeave, { passive: true });
    return () => {
      el.removeEventListener("mousemove", onMove);
      el.removeEventListener("mouseleave", onLeave);
    };
  }, [frameless, tiltX, tiltY]);

  useEffect(() => {
    if (!playIntro && hubPhase !== "done") {
      setHubPhase("done");
    }
  }, [playIntro, hubPhase]);

  useEffect(() => {
    if (!playIntro) return;
    if (!readyToReveal || hubPhase !== "intro") return;
    const wait = window.setTimeout(
      () => {
        burstStartedAtRef.current = performance.now();
        setHubPhase("burst");
      },
      Math.max(0, INTRO_MS - 400),
    );
    return () => clearTimeout(wait);
  }, [readyToReveal, hubPhase, playIntro]);

  useEffect(() => {
    if (hubPhase !== "burst") return;
    onBurstStart?.();
  }, [hubPhase, onBurstStart]);

  useEffect(() => {
    if (!playIntro) return;
    if (hubPhase !== "burst") return;
    const done = window.setTimeout(() => {
      setHubPhase("done");
      onIntroDone?.();
    }, BURST_MS);
    return () => clearTimeout(done);
  }, [hubPhase, onIntroDone, playIntro]);

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

  // Spike energy on signal burst then decay to baseline.
  useEffect(() => {
    setEnergy(1);
    const t = window.setTimeout(() => setEnergy(0.22), 2200);
    return () => window.clearTimeout(t);
  }, [signalCount]);

  // If no active agent, emit slow ambient particles around the hub.
  useEffect(() => {
    if (hubPhase !== "done") return;
    let cancelled = false;
    const id = window.setInterval(() => {
      if (cancelled) return;
      const burst = 2;
      const next: Array<{ id: string; end: Pt }> = [];
      for (let i = 0; i < burst; i++) {
        next.push({
          id: `idle-${Date.now()}-${i}`,
          end: {
            x: 50 + (Math.random() - 0.5) * 12,
            y: 50 + (Math.random() - 0.5) * 12,
          },
        });
      }
      setParticles((prev) => [...prev, ...next]);
      window.setTimeout(() => {
        setParticles((prev) => prev.filter((p) => !next.some((n) => n.id === p.id)));
      }, 1800);
    }, 5200);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [hubPhase]);

  return (
    <div
      ref={containerRef}
      className={
        frameless
          ? "relative h-full w-full overflow-hidden bg-transparent"
          : "relative h-full min-h-[min(480px,70vh)] w-full overflow-hidden rounded-3xl border border-[color:var(--nexus-hub-frame)] bg-[var(--nexus-bg)] shadow-inner"
      }
    >
      {/* Micro-parallax / depth wrapper */}
      <motion.div
        className="absolute inset-0"
        style={{
          transformStyle: "preserve-3d",
          rotateX,
          rotateY,
          scale,
          willChange: "transform",
        }}
      >
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_50%_40%,rgba(34,211,238,0.08),transparent_55%)]" />
        {hubPhase === "done" && (
          <div className="absolute inset-0 bg-[linear-gradient(rgba(34,211,238,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(34,211,238,0.035)_1px,transparent_1px)] bg-[length:24px_24px]" />
        )}
        <div className="absolute inset-0 opacity-[0.12] mix-blend-overlay bg-[radial-gradient(circle_at_20%_30%,rgba(255,255,255,0.15),transparent_50%)]" />

        {box.w > 0 && box.h > 0 && hubPhase !== "done" && (
          <RotatingSphereCanvas
            width={box.w}
            height={box.h}
            mode={hubPhase}
            burstStartedAt={burstStartedAtRef.current}
          />
        )}
        {box.w > 0 && box.h > 0 && hubPhase === "done" && (
          <div className="absolute inset-0 nexus-ambient-rings" aria-hidden>
            <AmbientRingsCanvas width={box.w} height={box.h} />
          </div>
        )}

        {/* Always-on scanning sweep (subtle) */}
        {!frameless && hubPhase === "done" ? (
          <motion.div
            className="pointer-events-none absolute inset-0 z-[6] nexus-scan-sweep"
            aria-hidden
            animate={{ backgroundPositionX: ["-140%", "140%"] }}
            transition={{
              duration: 10 - energy * 3.5,
              repeat: Infinity,
              ease: "linear",
              repeatDelay: 0.6,
            }}
            style={{ opacity: 0.12 + energy * 0.12 }}
          />
        ) : null}

        {hubPhase === "done" && (
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
        )}

        <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2">
          <CentralStar energy={energy} variant={frameless ? "loading" : "hub"} />
        </div>

        {hubPhase === "done" &&
          placed.map(({ node, pos }) => (
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

        {hubPhase === "done" && (
          <div className="absolute bottom-6 left-6 z-20 font-mono text-[10px] text-cyan-500/50">
            SYSTEM_CLOCK: {clock}
            <br />
            MESH_SYNC: STABLE // ENTROPY: 0.031
          </div>
        )}
      </motion.div>
    </div>
  );
}
