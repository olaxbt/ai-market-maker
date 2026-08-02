"use client";

import Link from "next/link";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

function Tile({
  title,
  body,
  href,
  cta,
}: {
  title: string;
  body: string;
  href: string;
  cta: string;
}) {
  return (
    <section className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">{title}</div>
      <p className="mt-2 text-[11px] text-[rgba(226,232,240,0.88)]">{body}</p>
      <div className="mt-3">
        <Link
          href={href}
          className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
        >
          {cta}
        </Link>
      </div>
    </section>
  );
}

export default function TradePage() {
  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="AI TRADE"
        subtitle="Run backtests, monitor live state, review paper fills."
        active="nexus"
      />

      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="text-[11px] text-[rgba(226,232,240,0.9)]">
            Start in <b>Research</b> for agentic backtests (Binance or Yahoo). Use <b>Monitor</b> for live state and{" "}
            <b>Paper</b> for the paper portfolio.
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              href="/console?view=research"
              className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
            >
              Open Research
            </Link>
            <Link
              href="/console?view=portfolio"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open Portfolio
            </Link>
            <Link
              href="/paper"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Open Paper
            </Link>
          </div>
        </section>

        <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Tile
            title="Research workspace"
            body="Run backtests and inspect supervisor output in the Nexus Research view."
            href="/console?view=research"
            cta="Open Research"
          />
          <Tile
            title="Portfolio"
            body="Watch live/paper balances, positions, and risk — not Research backtests."
            href="/console?view=portfolio"
            cta="Open Portfolio"
          />
          <Tile
            title="Paper portfolio"
            body="Inspect paper fills and account state."
            href="/paper"
            cta="Open Paper"
          />
          <Tile
            title="Futu quotes"
            body="HK/US quotes when Futu OpenD is connected (status badge shows connectivity)."
            href="/console?view=futu"
            cta="Open Futu"
          />
        </div>
      </div>
    </div>
  );
}
