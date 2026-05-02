"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

type Signal = {
  id: number;
  ts: number;
  provider: string;
  kind: string;
  title: string;
  body: string;
  ticker?: string | null;
};

function fmtTs(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

export default function PublicProviderPage({ params }: { params: { provider: string } }) {
  const provider = decodeURIComponent(params.provider ?? "");
  const [enabled, setEnabled] = useState(true);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function loadProfile() {
      setError(null);
      try {
        const res = await fetch(`/api/public/providers/${encodeURIComponent(provider)}/profile`, {
          cache: "no-store",
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(json?.detail || json?.error || "Failed to load profile");
        if (!cancelled) {
          setEnabled(Boolean(json?.enabled));
          const preview = Array.isArray(json?.signals_preview)
            ? (json.signals_preview as Signal[])
            : [];
          setSignals(preview);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load profile");
      }
    }
    void loadProfile();
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const sseUrl = useMemo(() => {
    const base = (process.env.NEXT_PUBLIC_FLOW_API_BASE_URL || "http://127.0.0.1:8001").replace(
      /\/$/,
      "",
    );
    return `${base}/signals/stream?provider=${encodeURIComponent(provider)}&poll_sec=1&limit=30`;
  }, [provider]);

  useEffect(() => {
    if (!provider) return;
    if (esRef.current) {
      esRef.current.close();
      esRef.current = null;
    }
    setError(null);
    const es = new EventSource(sseUrl);
    esRef.current = es;
    es.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg?.type === "signal" && msg?.signal) {
          const s = msg.signal as Signal;
          setSignals((prev) => {
            const next = [s, ...prev];
            const dedup = new Map<number, Signal>();
            for (const x of next) dedup.set(x.id, x);
            return Array.from(dedup.values())
              .sort((a, b) => b.id - a.id)
              .slice(0, 80);
          });
        }
      } catch {
        // ignore
      }
    };
    es.onerror = () => {
      setError("stream disconnected (refresh will retry)");
    };
    return () => {
      es.close();
    };
  }, [provider, sseUrl]);

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title={`PUBLIC · ${provider || "—"}`}
        subtitle="Realtime provider signals stream (SSE)."
        active="observe"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="text-[11px] text-[var(--nexus-muted)]">
            {enabled ? "stream enabled" : "public profile disabled on server"}
          </div>
          <div className="flex items-center gap-2">
            <Link
              href={`/leaderboard/providers/${encodeURIComponent(provider)}`}
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Full profile
            </Link>
            <Link
              href="/leaderboard?focus=signals"
              className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
            >
              Feed
            </Link>
          </div>
        </section>

        {error ? (
          <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        ) : null}

        <section className="mt-4 flex flex-col gap-3">
          {signals.map((s) => (
            <article
              key={s.id}
              className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-[rgba(226,232,240,0.9)]">
                    {s.kind}
                  </span>
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
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}
