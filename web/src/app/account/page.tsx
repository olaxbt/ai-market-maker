"use client";

import { NexusSectionHeader } from "@/components/NexusSectionHeader";
import { FirstRunChecklistPanel } from "@/components/FirstRunChecklistPanel";
import { SystemStatusPanel } from "@/components/SystemStatusPanel";
import Link from "next/link";

export default function AccountPage() {
  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="WORKSPACE"
        subtitle="Advanced: system status and first-run checklist."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">Where did tools go?</div>
          <div className="mt-2 text-[11px] text-[rgba(226,232,240,0.88)]">
            Approvals, Paper, and Provider keys are operator tools. They live under <b>Nexus</b> (Advanced).
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href="/inbox"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open approvals
            </Link>
            <Link
              href="/paper"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open paper
            </Link>
            <Link
              href="/platform/providers"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open provider keys
            </Link>
          </div>
        </section>
        <SystemStatusPanel />
        <div className="mt-3" />
        <FirstRunChecklistPanel />
      </div>
    </div>
  );
}

