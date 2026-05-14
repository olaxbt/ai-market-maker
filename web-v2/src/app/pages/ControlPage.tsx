import { useEffect, useState } from "react";
import { Link } from "react-router";

import { Button } from "../components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Separator } from "../components/ui/separator";

type Selftest = {
  ok?: boolean;
  runs?: { ok?: boolean; error?: string | null };
  db?: { configured?: boolean; ok?: boolean; error?: string | null };
};

type Capabilities = {
  mode_hint?: string;
  leaderboard?: {
    external_submit_requires_key?: boolean;
    external_submit_requires_signature?: boolean;
    provider_keys_configured?: boolean;
  };
  ops?: {
    can_run_backtests?: boolean;
    can_publish_backtest_via_ops?: boolean;
    runtime_settings_supported?: boolean;
  };
};

type RuntimeSettings = {
  path?: string;
  settings?: Record<string, any>;
};

function api(path: string) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `/api${p}`;
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium ${
        ok
          ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200"
          : "border-destructive/30 bg-destructive/10 text-destructive"
      }`}
    >
      {label}
    </span>
  );
}

/**
 * Flow diagnostics and runtime tuning only. Running backtests, publish, and receipts live under `/backtests`.
 */
export default function ControlPage() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [selftest, setSelftest] = useState<Selftest | null>(null);
  const [rt, setRt] = useState<RuntimeSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const hm = (rt?.settings?.harness_memory ?? {}) as Record<string, any>;
  const [hmViews, setHmViews] = useState<number>(60);
  const [hmDecisions, setHmDecisions] = useState<number>(60);
  const [hmTools, setHmTools] = useState<number>(60);
  const [hmSaving, setHmSaving] = useState(false);

  function refresh() {
    setError(null);
    Promise.all([
      fetch(api("/capabilities")).then((r) => r.json()),
      fetch(api("/ops/selftest")).then((r) => r.json()),
      fetch(api("/runtime-settings")).then((r) => r.json()),
    ])
      .then(([c, s, r]) => {
        setCaps(c ?? null);
        setSelftest(s ?? null);
        setRt(r ?? null);
      })
      .catch((e) => setError(e?.message || "Failed to load Control Center data"));
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setHmViews(Number(hm?.recent_views_max ?? 60));
    setHmDecisions(Number(hm?.recent_decisions_max ?? 60));
    setHmTools(Number(hm?.recent_tool_events_max ?? 60));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rt?.settings?.harness_memory]);

  async function saveHarnessMemory() {
    setError(null);
    setHmSaving(true);
    try {
      const res = await fetch(api("/runtime-settings/harness-memory"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          harness_memory: {
            recent_views_max: Number(hmViews),
            recent_decisions_max: Number(hmDecisions),
            recent_tool_events_max: Number(hmTools),
          },
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          (json as any)?.detail ||
            (json as any)?.error ||
            `Failed to save harness memory (${res.status})`,
        );
      }
      setRt(json ?? null);
    } catch (e: any) {
      setError(e?.message || "Failed to save harness memory");
    } finally {
      setHmSaving(false);
    }
  }

  const selfOk = Boolean(selftest?.ok);
  const modeHint = caps?.mode_hint ?? "unknown";

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Operations</p>
              <h2 className="mt-1 text-xl font-semibold tracking-tight">Control Center</h2>
              <p className="mt-1 max-w-xl text-sm text-muted-foreground">
                Flow diagnostics for operators: health checks, API capabilities, and receipt context limits.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md border border-border bg-muted/50 px-2.5 py-1 text-xs text-muted-foreground">
                mode <span className="font-mono text-foreground">{modeHint}</span>
              </span>
              <Button type="button" variant="outline" size="sm" onClick={refresh}>
                Refresh
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl space-y-6">
          {error ? (
            <div
              className="rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-destructive"
              role="alert"
            >
              {error}
            </div>
          ) : null}

          <div className="grid gap-4 sm:grid-cols-2">
            <Card id="cc-setup">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">Setup</CardTitle>
                  <StatusBadge ok={selfOk} label={selfOk ? "Healthy" : "Check logs"} />
                </div>
                <CardDescription>Local paths and database reachability</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Runs directory</span>
                  <code className="text-xs">{selftest?.runs?.ok ? "writable" : "issue"}</code>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Database</span>
                  <code className="text-xs">
                    {selftest?.db?.configured ? (selftest?.db?.ok ? "connected" : "error") : "not configured"}
                  </code>
                </div>
                {selftest?.runs?.error ? <p className="text-xs text-destructive">{selftest.runs.error}</p> : null}
                {selftest?.db?.error ? <p className="text-xs text-destructive">{selftest.db.error}</p> : null}
                <Separator />
                <div className="text-xs text-muted-foreground">
                  This page is intentionally diagnostics-only. Onboarding, guides, and access links live under Workspace.
                </div>
              </CardContent>
            </Card>

            <Card id="cc-capabilities">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <CardTitle className="text-base">Capabilities</CardTitle>
                  <StatusBadge
                    ok={Boolean(caps?.ops?.can_run_backtests)}
                    label={caps?.ops?.can_run_backtests ? "Backtests on" : "Backtests off"}
                  />
                </div>
                <CardDescription>What this Flow instance exposes to clients</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Submit needs API key</span>
                  <span>{caps?.leaderboard?.external_submit_requires_key ? "yes" : "no"}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Submit needs signature</span>
                  <span>{caps?.leaderboard?.external_submit_requires_signature ? "yes" : "no"}</span>
                </div>
                <div className="flex justify-between gap-3">
                  <span className="text-muted-foreground">Provider keys</span>
                  <span>{caps?.leaderboard?.provider_keys_configured ? "configured" : "not set"}</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card id="cc-harness">
            <CardHeader>
              <CardTitle className="text-base">Harness memory</CardTitle>
              <CardDescription>Receipt context limits for iteration logs (cost vs readability).</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-xs text-muted-foreground">
                {rt?.path ? (
                  <>
                    Using <code className="font-mono text-foreground">{rt.path}</code>
                  </>
                ) : (
                  "Runtime settings path not reported."
                )}
              </p>
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="space-y-2">
                  <Label htmlFor="hm-v">views_max</Label>
                  <Input
                    id="hm-v"
                    type="number"
                    min={1}
                    value={hmViews}
                    onChange={(e) => setHmViews(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="hm-d">decisions_max</Label>
                  <Input
                    id="hm-d"
                    type="number"
                    min={1}
                    value={hmDecisions}
                    onChange={(e) => setHmDecisions(Number(e.target.value))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="hm-t">tool_events_max</Label>
                  <Input
                    id="hm-t"
                    type="number"
                    min={1}
                    value={hmTools}
                    onChange={(e) => setHmTools(Number(e.target.value))}
                  />
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" onClick={saveHarnessMemory} disabled={hmSaving}>
                  {hmSaving ? "Saving…" : "Save"}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setHmViews(60);
                    setHmDecisions(60);
                    setHmTools(60);
                  }}
                >
                  Reset defaults
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
