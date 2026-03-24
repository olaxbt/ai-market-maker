"use client";

import { useEffect, useMemo, useRef, useState, type CSSProperties } from "react";

type Dot = {
  x: number;
  y: number;
  z: number;
  size: number;
  twinkleDelay: number;
  twinkleDuration: number;
  ex: number;
  ey: number;
  ez: number;
};

function sphereDots(count: number, spread: number): Dot[] {
  // Fibonacci sphere for visually even star distribution.
  const phi = Math.PI * (3 - Math.sqrt(5));
  const out: Dot[] = [];
  for (let i = 0; i < count; i++) {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = phi * i;
    const x = Math.cos(theta) * radius;
    const z = Math.sin(theta) * radius;
    out.push({
      x,
      y,
      z,
      size: 1.2 + Math.random() * 3.1,
      twinkleDelay: Math.random() * 2.5,
      twinkleDuration: 2.2 + Math.random() * 3.6,
      ex: Math.cos(theta) * spread,
      ey: y * spread,
      ez: Math.sin(theta) * spread * (0.25 + Math.random() * 1.2),
    });
  }
  return out;
}

interface NexusLoadingSphereProps {
  ready: boolean;
  onDone?: () => void;
}

const EXPLODE_MS = 1300;

export function NexusLoadingSphere({ ready, onDone }: NexusLoadingSphereProps) {
  const doneRef = useRef(false);
  const [explodeScale, setExplodeScale] = useState(1);
  const [isExploding, setIsExploding] = useState(false);
  const dots = useMemo(() => sphereDots(160, 420), []);

  useEffect(() => {
    const resize = () => {
      if (typeof window === "undefined") return;
      const diag = Math.hypot(window.innerWidth, window.innerHeight);
      setExplodeScale(Math.max(1, diag / 820));
    };
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  useEffect(() => {
    if (!ready || doneRef.current) return;
    doneRef.current = true;
    setIsExploding(true);
    const t = window.setTimeout(() => onDone?.(), EXPLODE_MS);
    return () => window.clearTimeout(t);
  }, [ready, onDone]);

  return (
    <div
      className={`nexus-loader-wrap ${isExploding ? "is-exploding" : ""}`}
      role="status"
      aria-live="polite"
      aria-label="Loading live flow"
    >
      <div className="nexus-loader-scene">
        <div className="nexus-loader-sphere">
          {dots.map((dot, idx) => (
            <span
              key={idx}
              className="nexus-loader-dot"
              style={
                {
                  "--x": `${dot.x * 132}px`,
                  "--y": `${dot.y * 132}px`,
                  "--z": `${dot.z * 132}px`,
                  "--ex": `${dot.ex * explodeScale}px`,
                  "--ey": `${dot.ey * explodeScale}px`,
                  "--ez": `${dot.ez * explodeScale}px`,
                  "--s": `${dot.size}px`,
                  "--delay": `${dot.twinkleDelay}s`,
                  "--twinkle-dur": `${dot.twinkleDuration}s`,
                } as CSSProperties
              }
            />
          ))}
          <div className="nexus-loader-core" />
        </div>
      </div>
      <p className="nexus-loader-text">Booting live flow stream...</p>
    </div>
  );
}

