import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, Loader2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

type NexusPayload = {
  metadata?: Record<string, unknown>;
  topology?: {
    nodes?: Array<Record<string, unknown>>;
  };
  traces?: Array<Record<string, unknown>>;
  agent_prompts?: Array<Record<string, unknown>>;
};

function asString(v: unknown) {
  return typeof v === "string" ? v : v === null || v === undefined ? "" : String(v);
}

function pretty(v: unknown) {
  try {
    return JSON.stringify(v, null, 2);
  } catch {
    return String(v);
  }
}

export default function AgentDetailPage() {
  const params = useParams();
  const nodeId = decodeURIComponent(asString((params as any)?.nodeId));

  const [payload, setPayload] = useState<NexusPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch("/api/runs/latest/payload?soft=1", { cache: "no-store" as any });
        const json = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || `Failed to load payload (${res.status})`);
        if (!cancelled) setPayload(json as any);
      } catch (e: any) {
        if (!cancelled) {
          setPayload(null);
          setError(e?.message || "Failed to load payload");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const node = useMemo(() => {
    const nodes = (payload?.topology?.nodes ?? []) as Array<Record<string, unknown>>;
    return nodes.find((n) => asString(n?.id) === nodeId) ?? null;
  }, [payload, nodeId]);

  const traces = useMemo(() => {
    const t = (payload?.traces ?? []) as Array<Record<string, unknown>>;
    return t.filter((x) => asString(x?.node_id) === nodeId);
  }, [payload, nodeId]);

  const promptDefaults = useMemo(() => {
    const ps = (payload?.agent_prompts ?? []) as Array<Record<string, unknown>>;
    return ps.find((p) => asString(p?.node_id) === nodeId) ?? null;
  }, [payload, nodeId]);

  const nodeTone = useMemo(() => {
    const st = asString(node?.status).toUpperCase();
    if (st === "ACTIVE" || st === "RUNNING") return "ok";
    if (st === "FAILED" || st === "ERROR") return "bad";
    if (st === "COMPLETED") return "done";
    return "muted";
  }, [node]);

  return (
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Agent</div>
            <h1 className="mt-1 text-[18px] font-semibold">
              {node?.label ? String(node.label) : nodeId || "—"}
            </h1>
            <p className="mt-1 text-[12px] text-muted-foreground">
              Standalone deep link; primary UX is inside Console → Agents.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to="/console?view=grid"
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Agents
            </Link>
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-4 py-3 text-[12px] text-[rgba(242,92,84,0.95)]">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="mt-4 inline-flex items-center gap-2 text-[12px] text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </div>
        ) : null}

        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="text-[14px]">Node</CardTitle>
              <CardDescription className="text-[12px]">From latest run payload topology</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-3 flex flex-wrap items-center gap-2 text-[12px]">
                <span
                  className={[
                    "rounded-lg border px-2 py-1 text-[10px]",
                    nodeTone === "ok"
                      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(0,212,170,0.92)]"
                      : nodeTone === "bad"
                        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
                        : nodeTone === "done"
                          ? "border-[rgba(99,102,241,0.20)] bg-[rgba(99,102,241,0.10)] text-[rgba(99,102,241,0.92)]"
                          : "border-border bg-muted/20 text-muted-foreground",
                  ].join(" ")}
                >
                  status: {asString(node?.status) || "—"}
                </span>
                <span className="rounded-lg border border-border bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
                  id: {nodeId || "—"}
                </span>
                {asString(node?.actor) ? (
                  <span className="rounded-lg border border-border bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground">
                    actor: {asString(node?.actor)}
                  </span>
                ) : null}
              </div>
              <pre className="max-h-[420px] overflow-auto rounded-xl border border-border bg-muted/20 p-3 text-[11px] text-foreground/90">
{pretty(node)}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-[14px]">Prompt defaults</CardTitle>
              <CardDescription className="text-[12px]">If configured for this node</CardDescription>
            </CardHeader>
            <CardContent>
              <pre className="max-h-[420px] overflow-auto rounded-xl border border-border bg-muted/20 p-3 text-[11px] text-foreground/90">
{pretty(promptDefaults)}
              </pre>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-[14px]">Summary</CardTitle>
              <CardDescription className="text-[12px]">Quick context</CardDescription>
            </CardHeader>
            <CardContent className="text-[12px] text-muted-foreground space-y-2">
              <div>
                <span className="text-foreground/80 font-semibold">Label:</span>{" "}
                {asString(node?.label) || "—"}
              </div>
              <div>
                <span className="text-foreground/80 font-semibold">Summary:</span>{" "}
                {asString(node?.summary) || "—"}
              </div>
              <div>
                <span className="text-foreground/80 font-semibold">Traces:</span> {traces.length}
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="mt-3">
          <CardHeader>
            <CardTitle className="text-[14px]">Traces ({traces.length})</CardTitle>
            <CardDescription className="text-[12px]">Most recent entries for this node</CardDescription>
          </CardHeader>
          <CardContent>
            {traces.length === 0 ? (
              <div className="text-[12px] text-muted-foreground">No traces for this node.</div>
            ) : (
              <div className="space-y-2">
                {traces
                  .slice(-40)
                  .reverse()
                  .map((t, idx) => {
                    const actorRole = asString((t as any)?.actor?.role) || asString((t as any)?.actor?.id);
                    const ts = (t as any)?.timestamp;
                    const content = (t as any)?.content;
                    return (
                      <div key={`${asString((t as any)?.trace_id) || idx}`} className="rounded-xl border border-border bg-muted/10 p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="text-[12px] font-semibold">
                            {actorRole || "trace"}{" "}
                            <span className="text-muted-foreground font-normal">
                              · {asString((t as any)?.trace_id) || "—"}
                            </span>
                          </div>
                          <div className="text-[11px] text-muted-foreground">{String(ts ? new Date(ts).toLocaleString() : "—")}</div>
                        </div>
                        <pre className="mt-2 max-h-[260px] overflow-auto rounded-xl border border-border bg-background/40 p-3 text-[11px] text-foreground/90">
{pretty(content)}
                        </pre>
                      </div>
                    );
                  })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

