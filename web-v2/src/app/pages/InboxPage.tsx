import { useEffect, useState } from "react";
import { Link } from "react-router";
import { LoginRequiredPanel } from "../components/LoginRequiredPanel";

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

export default function InboxPage({ embedded = false }: { embedded?: boolean }) {
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
      const res = await fetch("/api/social/inbox?limit=300", { cache: "no-store" as any });
      const json = await res.json().catch(() => ({}));
      if (res.status === 401) {
        setLoginRequired(true);
        setItems([]);
        return;
      }
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Failed to load inbox");
      setItems(Array.isArray((json as any)?.items) ? (json as any).items : []);
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
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Execute failed");
      const ok = Boolean((json as any)?.ok);
      const detail =
        typeof (json as any)?.execution?.detail === "string"
          ? (json as any).execution.detail
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
    <div className={embedded ? "px-4 pb-10 sm:px-6" : "flex-1 min-h-0 overflow-auto px-6 py-10"}>
      <div className="mx-auto w-full max-w-6xl">
        {embedded ? null : (
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Queue</div>
              <h1 className="mt-1 text-[18px] font-semibold">Approvals</h1>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Review provider ops updates and execute into your paper portfolio.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Link to="/ops?tab=paper" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
                Paper
              </Link>
              <Link
                to="/platform/providers"
                className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
              >
                Provider keys
              </Link>
            </div>
          </div>
        )}

        {loginRequired ? (
          <div className="mt-4">
            <LoginRequiredPanel body="Sign in to see followed provider updates and approve executions." />
          </div>
        ) : null}

        <section className="mt-4 rounded-2xl border border-border bg-card p-4">
          <div className="text-[12px] text-muted-foreground">{loading ? "Loading…" : `${items.length} items`}</div>
          {error ? (
            <div className="mt-3 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}
        </section>

        <section className="mt-4 flex flex-col gap-3">
          {!loading && items.length === 0 ? (
            <div className="rounded-2xl border border-border bg-card p-4 text-[12px] text-muted-foreground">
              No inbox items yet. Follow a provider, publish signals, and run the worker.
            </div>
          ) : null}

          {items.map((it) => (
            <article key={it.id} className="rounded-2xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-foreground/90">
                    {it.kind}
                  </span>
                  <Link
                    to={`/leaderboard/providers/${encodeURIComponent(it.provider)}`}
                    className="text-[12px] hover:underline"
                  >
                    {it.provider}
                  </Link>
                  {it.ticker ? <span className="text-[11px] text-muted-foreground">{it.ticker}</span> : null}
                </div>
                <div className="flex items-center gap-2">
                  {it.kind === "ops" ? (
                    <button
                      type="button"
                      onClick={() => execute(it.id)}
                      className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-3 py-1.5 text-[11px] hover:border-[rgba(0,212,170,0.42)]"
                    >
                      Execute (paper)
                    </button>
                  ) : null}
                  <div className="text-[11px] text-muted-foreground">{fmtTs(it.ts)}</div>
                </div>
              </div>
              <h2 className="mt-2 text-[14px] font-semibold">{it.title}</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-[12px] text-muted-foreground">{it.body}</p>
              {execStatus[it.id] ? (
                <div className="mt-3 text-[11px] text-muted-foreground">
                  execution: <span className="text-foreground/90">{execStatus[it.id]}</span>
                </div>
              ) : null}
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}

