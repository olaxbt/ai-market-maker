"use client";

import { Suspense, useState, lazy } from "react";
import Link from "next/link";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

const StrategyStudio = lazy(() => import("@/features/trade/StrategyStudio"));

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

type TradeTab = "hub" | "studio";

export default function TradePage() {
  const [tab, setTab] = useState<TradeTab>("hub");

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="AI TRADE"
        subtitle="One page: run, monitor, review results, read signals."
        active="nexus"
      />

      {/* ── Tab bar ── */}
      <div className="border-b border-[rgba(138,149,166,0.08)]">
        <div className="mx-auto flex max-w-6xl gap-0 px-4">
          <button
            onClick={() => setTab("hub")}
            className={`px-5 py-3 text-[11px] font-semibold tracking-[0.08em] transition-colors ${
              tab === "hub"
                ? "border-b-2 border-[rgba(0,212,170,0.6)] text-[rgba(226,232,240,0.95)]"
                : "text-[rgba(138,149,166,0.5)] hover:text-[rgba(226,232,240,0.75)]"
            }`}
          >
            Hub
          </button>
          <button
            onClick={() => setTab("studio")}
            className={`px-5 py-3 text-[11px] font-semibold tracking-[0.08em] transition-colors ${
              tab === "studio"
                ? "border-b-2 border-[rgba(0,212,170,0.6)] text-[rgba(226,232,240,0.95)]"
                : "text-[rgba(138,149,166,0.5)] hover:text-[rgba(226,232,240,0.75)]"
            }`}
          >
            Strategy Studio
          </button>
        </div>
      </div>

      {/* ── Hub tab ── */}
      {tab === "hub" && (
        <div className="mx-auto w-full max-w-6xl px-4 py-6">
          <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
            <div className="text-[11px] text-[rgba(226,232,240,0.9)]">
              If you&apos;re new: open <b>Account</b> first for the checklist. If you&apos;re operating: use Nexus
              for live console + monitor, and Leaderboard for results + signals.
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link
                href="/account"
                className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
              >
                Start here → Account
              </Link>
              <Link
                href="/console"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Open Nexus console
              </Link>
              <Link
                href="/leaderboard"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Open Leaderboard
              </Link>
            </div>
          </section>

          <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <Tile
              title="Run backtest"
              body="Backtests always run inside Research (backtest + supervisor)."
              href="/console?view=research"
              cta="Open Research"
            />
            <Tile
              title="Live monitor"
              body="Watch balances/positions and the latest system decisions (always-on ops)."
              href="/console?view=monitor"
              cta="Open Monitor"
            />
            <Tile
              title="Results"
              body="Compare performance across local runs and published providers."
              href="/leaderboard"
              cta="Open Results"
            />
            <Tile
              title="Signals"
              body="Read provider strategy notes and ops updates (global or provider-filtered)."
              href="/leaderboard?focus=signals"
              cta="Open Signals"
            />
          </div>
        </div>
      )}

      {/* ── Strategy Studio tab ── */}
      {tab === "studio" && (
        <Suspense
          fallback={
            <div className="flex h-[60vh] items-center justify-center text-[11px] text-[rgba(138,149,166,0.5)]">
              Loading Strategy Studio…
            </div>
          }
        >
          <StrategyStudio />
        </Suspense>
      )}
    </div>
  );
}
