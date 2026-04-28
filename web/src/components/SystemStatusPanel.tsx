"use client";

import { useEffect, useState } from "react";

type Status = "unknown" | "ok" | "degraded";

function Pill({ status, label }: { status: Status; label: string }) {
  const cls =
    status === "ok"
      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
      : status === "degraded"
        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
        : "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]";
  return (
    <span className={`rounded-lg border px-2 py-1 text-[9px] uppercase tracking-[0.16em] ${cls}`}>
      {label}
    </span>
  );
}

export function SystemStatusPanel() {
  const [flowApi, setFlowApi] = useState<Status>("unknown");
  const [leaderboard, setLeaderboard] = useState<Status>("unknown");

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/traces?limit=1", { cache: "no-store" });
        if (!cancelled) setFlowApi(res.ok ? "ok" : "degraded");
      } catch {
        if (!cancelled) setFlowApi("degraded");
      }
      try {
        const res = await fetch("/api/leadpage/leaderboard?limit=1", { cache: "no-store" });
        if (!cancelled) setLeaderboard(res.ok ? "ok" : "degraded");
      } catch {
        if (!cancelled) setLeaderboard("degraded");
      }
    }
    void check();
    const t = window.setInterval(check, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  return (
    <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
        System status
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Pill status={flowApi} label={`Flow API: ${flowApi}`} />
        <Pill status={leaderboard} label={`Leaderboard: ${leaderboard}`} />
        <span className="ml-auto text-[10px] text-[var(--nexus-muted)]">auto-refresh 15s</span>
      </div>
    </section>
  );
}

