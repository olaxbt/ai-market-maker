"use client";

import Link from "next/link";

export function RunBacktestPrompt({
  context = "flow",
}: {
  context?: "flow" | "agents" | "portfolio";
}) {
  const line =
    context === "agents"
      ? "Browse the roster anytime. Live session and Research can run together — Live for the book, Research to tune agents."
      : context === "portfolio"
        ? "Portfolio shows the live trading book. Backtest charts live in Research → Saved run."
        : "This map is the agent setup. Keep Live on for the book; use Research in parallel to fine-tune agent behaviour.";

  return (
    <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-b border-[color:var(--nexus-card-stroke)] bg-[rgba(0,212,170,0.06)] px-4 py-2.5">
      <p className="min-w-0 flex-1 text-[11px] leading-snug text-[var(--nexus-muted)]">
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)]">
          Setup ready
        </span>
        <span className="mx-2 text-[var(--nexus-rule-soft)]">·</span>
        {line}
      </p>
      <div className="flex flex-wrap gap-2">
        <Link
          href="/console?view=flow"
          className="shrink-0 rounded-lg border border-[color:var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/15 px-3.5 py-1.5 font-mono text-[10px] font-medium uppercase tracking-wider text-[var(--nexus-glow)] transition hover:bg-[var(--nexus-glow)]/25"
        >
          Live session controls ↑
        </Link>
        <Link
          href="/console?view=research"
          className="shrink-0 rounded-lg border border-[color:var(--nexus-card-stroke)] px-3.5 py-1.5 font-mono text-[10px] font-medium uppercase tracking-wider text-[var(--nexus-muted)] transition hover:text-[var(--nexus-text)]"
        >
          Research backtest
        </Link>
      </div>
    </div>
  );
}
