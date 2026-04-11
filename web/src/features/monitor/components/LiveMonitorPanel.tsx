"use client";

import { useEffect, useMemo, useState } from "react";
import type { NexusPayload } from "@/types/nexus-payload";

type PortfolioHealth = {
  account_id?: string;
  ts?: number;
  mode?: string;
  balances?: Record<string, number>;
  positions?: unknown[];
  risk_caps?: Record<string, unknown>;
  error?: string;
  hint?: string;
};

function fmtUsd(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return "—";
  return `$${x.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function LiveMonitorPanel({ payload }: { payload: NexusPayload | null }) {
  const [health, setHealth] = useState<PortfolioHealth | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        const res = await fetch("/api/pm/portfolio-health", { cache: "no-store" });
        const data = (await res.json().catch(() => ({}))) as PortfolioHealth;
        if (cancelled) return;
        if (!res.ok) {
          setErr(typeof data.error === "string" ? data.error : "Failed to load portfolio health");
          return;
        }
        setErr(null);
        setHealth(data);
      } catch {
        if (!cancelled) setErr("Failed to load portfolio health");
      }
    };
    void tick();
    const id = window.setInterval(() => void tick(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const balances = health?.balances ?? {};
  const usdt = typeof balances.USDT === "number" ? balances.USDT : null;
  const lastMsg = payload?.message_log?.[0]?.message ?? "—";
  const runId = payload?.metadata?.run_id ?? "—";
  const universeCount =
    payload?.metadata?.universe_size ??
    (Array.isArray(payload?.metadata?.universe_symbols)
      ? payload?.metadata?.universe_symbols.length
      : null);
  const status = payload?.metadata?.status ?? "—";

  const cards = useMemo(
    () => [
      { label: "Run", value: runId, tone: "text-[var(--nexus-glow)]" },
      { label: "Universe", value: universeCount == null ? "—" : String(universeCount), tone: "text-[var(--nexus-text)]" },
      { label: "Status", value: status, tone: "text-[var(--nexus-muted)]" },
      { label: "USDT balance", value: fmtUsd(usdt), tone: "text-[var(--nexus-text)]" },
    ],
    [runId, universeCount, status, usdt],
  );

  return (
    <div className="nexus-bg min-h-0 flex-1 overflow-auto">
      <div className="mx-auto w-full max-w-6xl px-4 pb-6 pt-10 space-y-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-glow)]">Operations</p>
            <h2 className="mt-1 text-lg font-semibold tracking-tight text-[var(--nexus-text)]">Live monitor</h2>
            <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-[var(--nexus-muted)]">
              Current balance/positions plus the last emitted decision from the live FlowEvent stream.
            </p>
          </div>
        </div>

        {err ? (
          <div className="rounded-lg border border-red-900/45 bg-red-950/35 px-4 py-3 font-mono text-xs text-red-100">
            {err}
          </div>
        ) : null}

        <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((c) => (
            <div
              key={c.label}
              className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 px-4 py-3 shadow-[0_0_24px_rgba(0,212,170,0.04)]"
            >
              <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">{c.label}</p>
              <p className={`mt-1 truncate font-mono text-sm ${c.tone}`} title={c.value}>
                {c.value}
              </p>
            </div>
          ))}
        </section>

        <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Last event</p>
          <p className="mt-2 font-mono text-[12px] leading-relaxed text-[var(--nexus-text)]">{lastMsg}</p>
        </section>

        <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Raw portfolio health</p>
          <pre className="mt-2 overflow-auto rounded-lg border border-[var(--nexus-rule-soft)] bg-[var(--nexus-bg)]/40 p-3 text-[11px] text-[var(--nexus-muted)]">
            {JSON.stringify(health ?? {}, null, 2)}
          </pre>
        </section>
      </div>
    </div>
  );
}

