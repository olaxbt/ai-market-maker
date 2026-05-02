"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { LoginRequiredPanel } from "@/components/LoginRequiredPanel";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

type InboxItem = {
  id: number;
  ts: number;
  signal_id: number;
  provider: string;
  kind: string;
  title: string;
  body: string;
  ticker?: string | null;
  read_ts?: number | null;
};

function fmtTs(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

export function InboxPage() {
  const [items, setItems] = useState<InboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loginRequired, setLoginRequired] = useState(false);
  const [execStatus, setExecStatus] = useState<Record<number, string>>({});

  async function load() {
    setLoading(true);
    setError(null);
    setLoginRequired(false);
    try {
      const res = await fetch("/api/social/inbox?limit=300", { cache: "no-store" });
      const json = await res.json().catch(() => ({}));
      if (res.status === 401) {
        setLoginRequired(true);
        setItems([]);
        return;
      }
      if (!res.ok) throw new Error(json?.detail || json?.error || "Failed to load inbox");
      setItems(Array.isArray(json?.items) ? json.items : []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    const t = window.setInterval(load, 10_000);
    return () => clearInterval(t);
  }, []);

  async function execute(inboxId: number) {
    setExecStatus((p) => ({ ...p, [inboxId]: "executing…" }));
    try {
      const res = await fetch("/api/copy/execute", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ inbox_id: inboxId }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || json?.error || "Execute failed");
      const ok = Boolean(json?.ok);
      const detail =
        typeof json?.execution?.detail === "string"
          ? json.execution.detail
          : ok
            ? "executed"
            : "failed";
      setExecStatus((p) => ({ ...p, [inboxId]: detail }));
      await load();
    } catch (e) {
      setExecStatus((p) => ({
        ...p,
        [inboxId]: e instanceof Error ? e.message : "Execute failed",
      }));
    }
  }

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="APPROVALS"
        subtitle="Your queue: review followed provider ops updates and execute into paper portfolio."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {loginRequired ? (
          <LoginRequiredPanel body="Your inbox is personal. Sign in to see followed provider updates and approve ops executions." />
        ) : null}
        <section className="mt-3 flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-[11px] text-[var(--nexus-muted)]">
              {loading ? "Loading…" : `${items.length} items`}
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/paper"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Paper portfolio
              </Link>
              <Link
                href="/platform/providers"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Publishing keys
              </Link>
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
        </section>

        <section className="mt-4 flex flex-col gap-3">
          {!loading && items.length === 0 ? (
            <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4 text-[11px] text-[var(--nexus-muted)]">
              No inbox items yet. Follow a provider, publish signals, and run the worker.
            </div>
          ) : null}

          {items.map((it) => (
            <article
              key={it.id}
              className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.9)]">
                    {it.kind}
                  </span>
                  <Link
                    href={`/leaderboard/providers/${encodeURIComponent(it.provider)}`}
                    className="text-[11px] text-[rgba(226,232,240,0.9)] hover:text-white"
                  >
                    {it.provider}
                  </Link>
                  {it.ticker ? (
                    <span className="text-[10px] text-[var(--nexus-muted)]">{it.ticker}</span>
                  ) : null}
                </div>
                <div className="flex items-center gap-2">
                  {it.kind === "ops" ? (
                    <button
                      type="button"
                      onClick={() => execute(it.id)}
                      className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-3 py-1.5 text-[10px] text-[rgba(226,232,240,0.92)] hover:border-[rgba(0,212,170,0.42)]"
                    >
                      Execute (paper)
                    </button>
                  ) : null}
                  <div className="text-[10px] text-[var(--nexus-muted)]">{fmtTs(it.ts)}</div>
                </div>
              </div>
              <h2 className="mt-2 text-[13px] font-semibold text-[rgba(226,232,240,0.95)]">
                {it.title}
              </h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-[11px] text-[rgba(226,232,240,0.84)]">
                {it.body}
              </p>
              {execStatus[it.id] ? (
                <div className="mt-3 text-[10px] text-[var(--nexus-muted)]">
                  execution:{" "}
                  <span className="text-[rgba(226,232,240,0.9)]">{execStatus[it.id]}</span>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}
