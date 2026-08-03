"use client";

import { NexusSectionHeader } from "@/components/NexusSectionHeader";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import Link from "next/link";

export default function AccountPage() {
  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="WORKSPACE"
        subtitle="System status and shortcuts into Research."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">Quick links</div>
          <div className="mt-2 text-[11px] text-[rgba(226,232,240,0.88)]">
            Start in <b>Research</b> for backtests. Use <b>Paper</b> for the paper portfolio.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href="/console?view=research"
              className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
            >
              Open Research
            </Link>
            <Link
              href="/paper"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open paper
            </Link>
          </div>
        </section>
        <SystemStatusPanel />
      </div>
    </div>
  );
}
