import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router";

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

function flowBase(): string {
  const raw = ((import.meta as any)?.env?.VITE_FLOW_API_BASE_URL as string | undefined) || "http://127.0.0.1:8001";
  return raw.replace(/\/$/, "");
}

export default function PublicProviderPage() {
  const params = useParams();
  const provider = params.provider ? decodeURIComponent(String(params.provider)) : "";
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
          cache: "no-store" as any,
        });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Failed to load profile");
        if (!cancelled) {
          setEnabled(Boolean((json as any)?.enabled));
          const preview = Array.isArray((json as any)?.signals_preview) ? ((json as any).signals_preview as Signal[]) : [];
          setSignals(preview);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load profile");
      }
    }
    if (provider) void loadProfile();
    return () => {
      cancelled = true;
    };
  }, [provider]);

  const sseUrl = useMemo(() => {
    return `${flowBase()}/signals/stream?provider=${encodeURIComponent(provider)}&poll_sec=1&limit=30`;
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
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Public · {provider || "—"}
            </div>
            <h1 className="mt-1 text-[18px] font-semibold">Realtime provider signals (SSE)</h1>
            <p className="mt-1 text-[12px] text-muted-foreground">
              {enabled ? "stream enabled" : "public profile disabled on server"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/leaderboard/providers/${encodeURIComponent(provider)}`}
              className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
            >
              Full profile
            </Link>
            <Link
              to="/leaderboard?focus=signals"
              className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
            >
              Feed
            </Link>
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        ) : null}

        <section className="mt-4 flex flex-col gap-3">
          {signals.map((s) => (
            <article key={s.id} className="rounded-2xl border border-border bg-card p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] px-2 py-1 text-[10px] uppercase tracking-[0.16em] text-foreground/90">
                    {s.kind}
                  </span>
                  {s.ticker ? <span className="text-[11px] text-muted-foreground">{s.ticker}</span> : null}
                </div>
                <div className="text-[11px] text-muted-foreground">{fmtTs(s.ts)}</div>
              </div>
              <h2 className="mt-2 text-[14px] font-semibold">{s.title}</h2>
              <p className="mt-2 whitespace-pre-wrap break-words text-[12px] text-muted-foreground">{s.body}</p>
            </article>
          ))}
        </section>
      </div>
    </div>
  );
}

