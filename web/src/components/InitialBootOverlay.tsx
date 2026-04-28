"use client";

import { useEffect, useState } from "react";
import { NexusStarSystem } from "@/features/nexus";

export const NEXUS_BOOT_KEY = "nexus_boot_done_v1";

export function InitialBootOverlay() {
  const [show, setShow] = useState(false);
  const [bursting, setBursting] = useState(false);

  useEffect(() => {
    try {
      const done = sessionStorage.getItem(NEXUS_BOOT_KEY) === "1";
      if (done) return;
      sessionStorage.setItem(NEXUS_BOOT_KEY, "1");
      setShow(true);
    } catch {
      // If storage is blocked, fall back to a single short overlay.
      setShow(true);
    }
  }, []);

  if (!show) return null;
  return (
    <div
      className={`fixed inset-0 z-50 transition-[background-color,opacity] duration-700 ${
        bursting
          ? "pointer-events-none bg-transparent opacity-0"
          : "bg-[var(--nexus-bg)] opacity-100"
      }`}
    >
      <NexusStarSystem
        nodes={[]}
        edges={[]}
        activeNodeId={null}
        signalCount={0}
        readyToReveal
        onBurstStart={() => setBursting(true)}
        onIntroDone={() => {
          setShow(false);
          setBursting(false);
        }}
        playIntro
        frameless
      />
    </div>
  );
}
