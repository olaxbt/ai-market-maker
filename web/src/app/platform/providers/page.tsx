"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { LoginRequiredPanel } from "@/components/LoginRequiredPanel";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

function CurlBlock({
  baseUrl,
  provider,
  secret,
}: {
  baseUrl: string;
  provider: string;
  secret: string;
}) {
  const target = useMemo(
    () =>
      `${baseUrl.replace(/\/$/, "")}/leaderboard/providers/${encodeURIComponent(provider)}/results`,
    [baseUrl, provider],
  );
  const body = useMemo(
    () =>
      JSON.stringify(
        {
          provider,
          run_id: "example-run-001",
          schema_version: 1,
          total_return_pct: 1.2,
          sharpe: 1.1,
          max_drawdown_pct: 3.4,
          trade_count: 17,
          meta: { note: "example payload" },
        },
        null,
        2,
      ),
    [provider],
  );

  const cmd = useMemo(() => {
    const lines = [
      `curl -X POST "${target}"`,
      `  -H "Content-Type: application/json"`,
      `  -H "x-leadpage-provider-key: ${secret}"`,
      `  -d '${body}'`,
    ];
    return lines.join("\n");
  }, [body, secret, target]);

  return (
    <pre className="mt-2 whitespace-pre-wrap break-words rounded-xl border border-[rgba(138,149,166,0.22)] bg-[rgba(0,0,0,0.25)] p-3 text-[10px] text-[rgba(226,232,240,0.9)]">
      {cmd}
    </pre>
  );
}

export default function ProviderAdmin() {
  const [providers, setProviders] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newProvider, setNewProvider] = useState("");
  const [revealSecret, setRevealSecret] = useState<Record<string, string>>({});
  const [autoExecute, setAutoExecute] = useState<Record<string, boolean>>({});
  const [apiBase, setApiBase] = useState("http://127.0.0.1:8001");
  const [loginRequired, setLoginRequired] = useState(false);

  async function refresh() {
    setError(null);
    setLoginRequired(false);
    const res = await fetch("/api/platform/providers", { cache: "no-store" });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) setLoginRequired(true);
      setError(json?.detail || json?.error || "Failed to load providers");
      setProviders([]);
      return;
    }
    setProviders(Array.isArray(json?.providers) ? json.providers : []);
  }

  useEffect(() => {
    void refresh();
  }, []);

  async function createProvider() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/platform/providers", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ provider: newProvider }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || json?.error || "Create provider failed");
      if (typeof json?.provider === "string" && typeof json?.secret === "string") {
        setRevealSecret((prev) => ({ ...prev, [json.provider]: json.secret }));
      }
      setNewProvider("");
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Create provider failed");
    } finally {
      setBusy(false);
    }
  }

  async function rotate(provider: string) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(
        `/api/platform/providers/${encodeURIComponent(provider)}/rotate-secret`,
        {
          method: "POST",
        },
      );
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || json?.error || "Rotate failed");
      if (typeof json?.secret === "string") {
        setRevealSecret((prev) => ({ ...prev, [provider]: json.secret }));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Rotate failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggleAutoExecute(provider: string, next: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/copy/settings`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          provider,
          enabled: true,
          auto_execute: next,
          instrument: "spot",
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || json?.error || "Failed to update copy settings");
      setAutoExecute((p) => ({ ...p, [provider]: next }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update copy settings");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="PUBLISHING KEYS"
        subtitle="Create publisher ids, rotate keys, and publish results/signals into the platform."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {loginRequired ? (
          <LoginRequiredPanel body="Provider management is restricted. Sign in to create providers and rotate publish keys." />
        ) : null}
        <section className="mt-3 flex flex-col gap-3 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="text-[11px] text-[var(--nexus-muted)]">
              Manage publishing keys. Paper executions and approvals fanout require the worker.
            </div>
            <div className="flex items-center gap-2">
              <Link
                href="/paper"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Paper portfolio
              </Link>
              <Link
                href="/platform/login"
                className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
              >
                Login
              </Link>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <div className="md:col-span-2">
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Create publisher id
              </div>
              <div className="mt-2 flex gap-2">
                <input
                  value={newProvider}
                  onChange={(e) => setNewProvider(e.target.value)}
                  placeholder="publisher id (e.g. desk-a)"
                  className="nexus-prompt-input w-full rounded-xl px-3 py-2 text-[12px]"
                />
                <button
                  type="button"
                  onClick={createProvider}
                  disabled={busy || !newProvider.trim()}
                  className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)] disabled:opacity-50"
                >
                  Create
                </button>
              </div>
            </div>

            <div>
              <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                Backend base URL
              </div>
              <input
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="http://127.0.0.1:8001"
                className="mt-2 nexus-prompt-input w-full rounded-xl px-3 py-2 text-[12px]"
              />
            </div>
          </div>

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
        </section>

        <section className="mt-4 rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/45 p-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
            Your providers
          </div>

          {providers.length === 0 ? (
            <div className="mt-3 text-[11px] text-[var(--nexus-muted)]">
              No providers yet (or you’re not logged in).
            </div>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {providers.map((p) => (
                <div
                  key={p}
                  className="rounded-2xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.32)] p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.95)]">
                      {p}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleAutoExecute(p, !Boolean(autoExecute[p]))}
                        disabled={busy}
                        className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white disabled:opacity-50"
                        title="Auto-execute ops intents for followers when worker runs with PLATFORM_WORKER_AUTO_EXECUTE=1"
                      >
                        Auto-exec: {autoExecute[p] ? "ON" : "OFF"}
                      </button>
                      <Link
                        href={`/leaderboard/providers/${encodeURIComponent(p)}`}
                        className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
                      >
                        View
                      </Link>
                      <button
                        type="button"
                        onClick={() => rotate(p)}
                        disabled={busy}
                        className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.92)] hover:border-[rgba(0,212,170,0.42)] disabled:opacity-50"
                      >
                        Rotate key
                      </button>
                    </div>
                  </div>

                  {revealSecret[p] ? (
                    <div className="mt-3">
                      <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
                        Provider key (shown once)
                      </div>
                      <div className="mt-2 rounded-xl border border-[rgba(138,149,166,0.22)] bg-[rgba(0,0,0,0.25)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.92)] break-words">
                        {revealSecret[p]}
                      </div>
                      <CurlBlock baseUrl={apiBase} provider={p} secret={revealSecret[p]} />
                    </div>
                  ) : (
                    <div className="mt-3 text-[11px] text-[var(--nexus-muted)]">
                      Rotate key to reveal a publish token and a ready-to-run curl command.
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
