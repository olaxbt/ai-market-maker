import { useEffect, useMemo, useState } from "react";

type ToolDef = {
  id: string;
  title?: string;
  category?: string;
  description?: string;
  http?: { method: string; path: string };
};

export default function ToolsPage() {
  const [tools, setTools] = useState<ToolDef[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [q, setQ] = useState("");

  useEffect(() => {
    fetch(`/api/tools`, { cache: "no-store" as any })
      .then((r) => r.json())
      .then((d) => setTools(Array.isArray(d?.tools) ? d.tools : []))
      .catch((e) => setError(e?.message || "Failed to load tools"));
  }, []);

  const filtered = useMemo(() => {
    const qq = q.trim().toLowerCase();
    if (!qq) return tools;
    return tools.filter((t) => {
      const hay = [
        t.id,
        t.title ?? "",
        t.category ?? "",
        t.description ?? "",
        t.http?.method ?? "",
        t.http?.path ?? "",
      ]
        .join(" ")
        .toLowerCase();
      return hay.includes(qq);
    });
  }, [tools, q]);

  return (
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Tool Browser
            </div>
            <h1 className="mt-1 text-[18px] font-semibold">Platform Tools</h1>
            <div className="mt-1 text-[11px] text-muted-foreground">
              Source: Flow API <code>/tools</code> (proxied via <code>/api/tools</code>)
            </div>
          </div>
          <div className="w-full sm:w-[340px]">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Search tools…"
              className="w-full rounded-xl border border-border bg-card px-3 py-2 text-[12px] outline-none placeholder:text-muted-foreground"
            />
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-[rgba(242,92,84,0.25)] bg-[rgba(242,92,84,0.08)] px-4 py-3 text-[12px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        )}

        <div className="mt-6 space-y-2">
          {filtered.map((t) => (
            <div
              key={t.id}
              className="rounded-xl border border-border bg-card px-4 py-3"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <div className="text-[12px] font-semibold">
                      {t.title || t.id}
                    </div>
                    {t.category && (
                      <div className="rounded-md border border-[rgba(99,102,241,0.18)] bg-[rgba(99,102,241,0.10)] px-1.5 py-0.5 text-[9px] uppercase tracking-[0.14em] text-[rgba(99,102,241,0.8)]">
                        {t.category}
                      </div>
                    )}
                  </div>
                  <div className="mt-1 text-[11px] text-muted-foreground">
                    <code>{t.id}</code>
                  </div>
                  {t.description && (
                    <div className="mt-2 text-[12px] text-muted-foreground">
                      {t.description}
                    </div>
                  )}
                </div>
                {t.http && (
                  <div className="shrink-0 rounded-lg border border-[rgba(0,212,170,0.16)] bg-[rgba(0,212,170,0.07)] px-2 py-1 text-[10px] text-[rgba(0,212,170,0.9)]">
                    <code>
                      {t.http.method} {t.http.path}
                    </code>
                  </div>
                )}
              </div>
            </div>
          ))}

          {filtered.length === 0 && (
            <div className="rounded-xl border border-border bg-card px-4 py-10 text-center text-[12px] text-muted-foreground">
              No tools found.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

