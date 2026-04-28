"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: "strategy" | "ops" | "discussion" | string;
  title: string;
  body: string;
  ticker?: string | null;
  result_provider?: string | null;
  result_run_id?: string | null;
};

function fmtTs(ts: number) {
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

export function FeedPage() {
  const searchParams = useSearchParams();
  const providerParam = (searchParams.get("provider") ?? "").trim();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [kind, setKind] = useState<"all" | "strategy" | "ops" | "discussion">("all");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const qs = new URLSearchParams({ limit: "200" });
        if (providerParam) qs.set("provider", providerParam);
        const res = await fetch(`/api/signals/feed?${qs.toString()}`, { cache: "no-store" });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(json?.detail || json?.error || "Failed to load feed");
        const rows = Array.isArray(json?.signals) ? (json.signals as Signal[]) : [];
        if (!cancelled) setSignals(rows);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load feed");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    const t = window.setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [providerParam]);

  const filtered = useMemo(() => {
    if (kind === "all") return signals;
    return signals.filter((s) => s.kind === kind);
  }, [signals, kind]);

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title={providerParam ? `SIGNALS · ${providerParam}` : "SIGNALS"}
        subtitle="Provider-published strategy notes, ops updates, and discussions."
        active="observe"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <section className="flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
              <Link
                href="/leadpage"
                className="nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition"
              >
                Results
              </Link>
              <span className="nexus-segment-btn is-active rounded-lg px-3 py-1.5 text-[11px]">
                Signals
              </span>
            </div>
            <div className="ml-auto flex flex-wrap items-center gap-2">
              {providerParam ? (
                <>
                  <span className="rounded-lg border border-[rgba(34,211,238,0.22)] bg-[rgba(34,211,238,0.08)] px-2 py-1 text-[9px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.92)]">
                    provider: {providerParam}
                  </span>
                  <Link
                    href="/leadpage?focus=signals"
                    className="text-[10px] text-[var(--nexus-muted)] underline hover:text-white"
                    title="Clear provider filter"
                  >
                    clear
                  </Link>
                </>
              ) : (
                <span className="text-[10px] text-[var(--nexus-muted)]">global</span>
              )}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] text-[var(--nexus-muted)]">Filter</span>
            <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
              {(["all", "strategy", "ops", "discussion"] as const).map((k) => (
                <button
                  key={k}
                  type="button"
                  onClick={() => setKind(k)}
                  className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
                    kind === k ? "is-active" : ""
                  }`}
                >
                  {k}
                </button>
              ))}
            </div>
            <span className="ml-auto text-[11px] text-[var(--nexus-muted)]">
              {loading ? "Loading…" : `${filtered.length} items`}
            </span>
          </div>

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
        </section>

        <section className="mt-4 flex flex-col gap-3">
          {!loading && filtered.length === 0 ? (
            <div className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4 text-[11px] text-[var(--nexus-muted)]">
              No signals yet. Providers can publish to <code>/signals/publish</code>.
            </div>
          ) : null}

          {filtered.map((s) => (
            <article
              key={s.id}
              className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.9)]">
                    {s.kind}
                  </span>
                  <Link
                    href={`/leadpage/providers/${encodeURIComponent(s.provider)}`}
                    className="text-[11px] text-[rgba(226,232,240,0.9)] hover:text-white"
                  >
                    {s.provider}
                  </Link>
                  {s.ticker ? (
                    <span className="text-[10px] text-[var(--nexus-muted)]">{s.ticker}</span>
                  ) : null}
                </div>
                <div className="text-[10px] text-[var(--nexus-muted)]">{fmtTs(s.ts)}</div>
              </div>
              <h2 className="mt-2 text-[13px] font-semibold text-[rgba(226,232,240,0.95)]">
                {s.title}
              </h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-[11px] text-[rgba(226,232,240,0.84)]">
                {s.body}
              </p>
              {s.result_provider && s.result_run_id ? (
                <div className="mt-3 text-[10px] text-[var(--nexus-muted)]">
                  linked result:{" "}
                  <span className="text-[rgba(226,232,240,0.9)]">
                    {s.result_provider}/{s.result_run_id}
                  </span>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}
