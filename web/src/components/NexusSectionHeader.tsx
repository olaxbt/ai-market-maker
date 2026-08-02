"use client";

import { Suspense } from "react";
import { NexusHeaderNav, type HeaderNavMode } from "@/components/NexusHeaderNav";

function SectionExplainer({ active }: { active: HeaderNavMode }) {
  const text =
    active === "observe"
      ? "Signals feed for published activity."
      : "Browse Live desk and Agents anytime — that is the desk setup. Start a Live session for realtime thoughts, or Research for historical replays.";

  return (
    <div className="w-full overflow-hidden rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] leading-snug text-[rgba(226,232,240,0.82)]">
      <span className="text-[var(--nexus-muted)]">Tip</span> {text}
    </div>
  );
}

export function NexusSectionHeader({
  title,
  subtitle,
  active,
}: {
  title: string;
  subtitle: string;
  active: HeaderNavMode;
}) {
  return (
    <header className="relative border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
      <div className="w-full">
        <div className="min-w-0">
          <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">
            {title}
          </h1>
          <p className="mt-0.5 text-[10px] leading-snug tracking-wide text-[var(--nexus-muted)]">
            {subtitle}
          </p>
        </div>

        <div className="mt-2 border-t border-[var(--nexus-rule-soft)] pt-2">
          <Suspense fallback={<div className="h-10 w-full max-w-md rounded-lg bg-[rgba(6,8,11,0.35)]" />}>
            <NexusHeaderNav />
          </Suspense>
        </div>

        <div className="mt-2">
          <SectionExplainer active={active} />
        </div>
      </div>
    </header>
  );
}
