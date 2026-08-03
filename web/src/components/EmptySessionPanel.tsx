"use client";

import Link from "next/link";

export function EmptySessionPanel({
  title = "Nothing is running yet",
  body = "Start a Live session for the book, or open Research to run a backtest.",
  primaryHref = "/console?view=research",
  primaryLabel = "Go to Research",
}: {
  title?: string;
  body?: string;
  primaryHref?: string;
  primaryLabel?: string;
}) {
  return (
    <div className="flex min-h-[60vh] flex-1 items-center justify-center px-6 py-10">
      <div className="w-full max-w-lg rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/80 p-6 text-center shadow-[0_0_40px_rgba(0,0,0,0.25)]">
        <div className="inline-flex items-center gap-2 rounded-full border border-[rgba(138,149,166,0.2)] bg-[rgba(138,149,166,0.08)] px-3 py-1 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
          Session · idle
        </div>
        <h2 className="mt-4 text-lg font-semibold text-[var(--nexus-text)]">{title}</h2>
        <p className="mt-2 text-[12px] leading-relaxed text-[var(--nexus-muted)]">{body}</p>
        <Link
          href={primaryHref}
          className="mt-5 inline-flex rounded-xl border border-[color:var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/15 px-5 py-2.5 font-mono text-[11px] font-medium uppercase tracking-wider text-[var(--nexus-glow)] transition hover:bg-[var(--nexus-glow)]/25"
        >
          {primaryLabel}
        </Link>
      </div>
    </div>
  );
}
