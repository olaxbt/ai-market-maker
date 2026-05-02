"use client";

import { Suspense } from "react";
import { NexusHeaderNav, type HeaderNavMode } from "@/components/NexusHeaderNav";
import Link from "next/link";
import { useEffect, useState } from "react";
import { NEXUS_LAST_RUN_ID_KEY } from "@/components/NexusConsoleHeader";

function SectionExplainer({ active }: { active: HeaderNavMode }) {
  const text =
    active === "observe"
      ? "Leaderboard = performance + signals. Use Results to compare runs/providers; use Signals to see what they’re doing now."
      : "Nexus = operator tools. Research runs backtests; Monitor watches live state; Approvals/Paper are your paper-only ops loop.";

  return (
    <div className="w-full rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.82)]">
      <span className="text-[var(--nexus-muted)]">What is this?</span> {text}
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
  const [lastRunId, setLastRunId] = useState<string | null>(null);
  const [authed, setAuthed] = useState<boolean | null>(null);
  useEffect(() => {
    try {
      const v = sessionStorage.getItem(NEXUS_LAST_RUN_ID_KEY);
      setLastRunId(v ? String(v) : null);
    } catch {
      setLastRunId(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/platform/providers", { cache: "no-store" });
        if (!cancelled) setAuthed(res.status !== 401);
      } catch {
        if (!cancelled) setAuthed(null);
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <header className="border-b border-[var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm px-4 py-2.5">
      <div className="w-full">
        <div className="w-full flex flex-wrap items-center justify-start gap-3">
          <div className="min-w-0">
            <h1 className="text-sm font-bold tracking-[0.2em] text-[var(--nexus-glow)] nexus-glow-text">
              {title}
            </h1>
            <p className="mt-0.5 text-[10px] tracking-wide text-[var(--nexus-muted)]">{subtitle}</p>
          </div>
        </div>

        <div className="w-full mt-2 border-t border-[var(--nexus-rule-soft)] pt-2 flex flex-wrap items-center justify-start gap-3">
          <Suspense fallback={<div className="h-10 w-full max-w-md rounded-lg bg-[rgba(6,8,11,0.35)]" />}>
            <NexusHeaderNav active={active} variant="section" />
          </Suspense>
          {active !== "nexus" && lastRunId ? (
            <div className="rounded-lg border border-[rgba(138,149,166,0.18)] bg-[rgba(0,0,0,0.15)] px-2 py-1 text-[10px] text-[var(--nexus-muted)]">
              Run: <span className="text-[rgba(226,232,240,0.92)]">{lastRunId}</span>
            </div>
          ) : null}
          {authed === false ? (
            <Link
              href="/platform/login"
              className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
              title="Sign in to access approvals, paper, and publishing"
            >
              Sign in
            </Link>
          ) : null}
        </div>

        <div className="mt-2">
          <SectionExplainer active={active} />
        </div>
      </div>
    </header>
  );
}
