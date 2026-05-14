import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";
import { LoginRequiredPanel } from "../components/LoginRequiredPanel";

type ToolDef = {
  id: string;
  title?: string;
  category?: string;
  description?: string;
  http?: { method: string; path: string };
};

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
    () => `${baseUrl.replace(/\/$/, "")}/leaderboard/providers/${encodeURIComponent(provider)}/results`,
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
    <pre className="mt-2 whitespace-pre-wrap break-words rounded-xl border border-border bg-muted/30 p-3 text-[11px]">
      {cmd}
    </pre>
  );
}

export default function PlatformProvidersPage({ embedded = false }: { embedded?: boolean }) {
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
    const res = await fetch("/api/platform/providers", { cache: "no-store" as any });
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) setLoginRequired(true);
      setError((json as any)?.detail || (json as any)?.error || "Failed to load providers");
      setProviders([]);
      return;
    }
    setProviders(Array.isArray((json as any)?.providers) ? (json as any).providers : []);
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
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Create provider failed");
      if (typeof (json as any)?.provider === "string" && typeof (json as any)?.secret === "string") {
        setRevealSecret((prev) => ({ ...prev, [(json as any).provider]: (json as any).secret }));
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
      const res = await fetch(`/api/platform/providers/${encodeURIComponent(provider)}/rotate-secret`, {
        method: "POST",
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Rotate failed");
      if (typeof (json as any)?.secret === "string") {
        setRevealSecret((prev) => ({ ...prev, [provider]: (json as any).secret }));
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
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Failed to update copy settings");
      setAutoExecute((p) => ({ ...p, [provider]: next }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update copy settings");
    } finally {
      setBusy(false);
    }
  }

  const body = (
    <div className={`${embedded ? "" : "mx-auto w-full max-w-6xl"}`}>
      {embedded ? null : (
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Publishing Keys</div>
            <h1 className="mt-1 text-[18px] font-semibold">Providers</h1>
            <p className="mt-1 text-[12px] text-muted-foreground">
              Create publisher ids, rotate keys, and publish results/signals into the platform.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link to="/ops?tab=paper" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
              Paper
            </Link>
            <Link to="/platform/login" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
              Login
            </Link>
          </div>
        </div>
      )}

      {loginRequired ? (
        <div className="mt-4">
          <LoginRequiredPanel body="Sign in to create providers and rotate publish keys." />
        </div>
      ) : null}

      <section className={`${embedded ? "" : "mt-4 "}rounded-lg border border-border bg-card p-4`}>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="md:col-span-2">
              <div className="text-[11px] font-semibold">Create publisher id</div>
              <div className="mt-2 flex gap-2">
                <input
                  value={newProvider}
                  onChange={(e) => setNewProvider(e.target.value)}
                  placeholder="publisher id (e.g. desk-a)"
                  className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] outline-none"
                />
                <button
                  type="button"
                  onClick={createProvider}
                  disabled={busy || !newProvider.trim()}
                  className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold hover:border-[rgba(0,212,170,0.45)] disabled:opacity-50"
                >
                  Create
                </button>
              </div>
            </div>

            <div>
              <div className="text-[11px] font-semibold">Backend base URL</div>
              <input
                value={apiBase}
                onChange={(e) => setApiBase(e.target.value)}
                placeholder="http://127.0.0.1:8001"
                className="mt-2 w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] outline-none"
              />
            </div>
          </div>

          {error ? (
            <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
      </section>

      <section className="mt-4 rounded-lg border border-border bg-card p-4">
          <div className="text-[11px] font-semibold">Your providers</div>
          {providers.length === 0 ? (
            <div className="mt-3 text-[12px] text-muted-foreground">No providers yet (or you’re not logged in).</div>
          ) : (
            <div className="mt-3 flex flex-col gap-3">
              {providers.map((p) => (
                <div key={p} className="rounded-2xl border border-border bg-muted/20 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[13px] font-semibold">{p}</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => toggleAutoExecute(p, !Boolean(autoExecute[p]))}
                        disabled={busy}
                        className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30 disabled:opacity-50"
                        title="Auto-execute ops intents for followers when worker runs with PLATFORM_WORKER_AUTO_EXECUTE=1"
                      >
                        Auto-exec: {autoExecute[p] ? "ON" : "OFF"}
                      </button>
                      <Link
                        to={`/leaderboard/providers/${encodeURIComponent(p)}`}
                        className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
                      >
                        View
                      </Link>
                      <button
                        type="button"
                        onClick={() => rotate(p)}
                        disabled={busy}
                        className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[12px] hover:border-[rgba(0,212,170,0.42)] disabled:opacity-50"
                      >
                        Rotate key
                      </button>
                    </div>
                  </div>

                  {revealSecret[p] ? (
                    <div className="mt-3">
                      <div className="text-[11px] font-semibold">Provider key (shown once)</div>
                      <div className="mt-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] break-words">
                        {revealSecret[p]}
                      </div>
                      <CurlBlock baseUrl={apiBase} provider={p} secret={revealSecret[p]} />
                    </div>
                  ) : (
                    <div className="mt-3 text-[12px] text-muted-foreground">
                      Rotate key to reveal a publish token and a ready-to-run curl command.
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
      </section>
    </div>
  );

  if (embedded) return body;
  return <div className="flex-1 min-h-0 overflow-auto px-6 py-10">{body}</div>;
}

