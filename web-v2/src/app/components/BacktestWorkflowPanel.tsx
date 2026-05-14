import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router";
import { ChevronDown } from "lucide-react";

import { Button } from "./ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { cn } from "./ui/utils";

type OpsBacktestResponse = {
  run_id?: string;
  trade_count?: number;
  metrics?: Record<string, unknown>;
};

type BacktestJob =
  | { status: "queued" | "running"; step?: number; total_steps?: number; trade_count?: number; equity?: number | null; capital?: number | null; positions?: number; ts?: number | null }
  | { status: "completed"; result?: OpsBacktestResponse }
  | { status: "failed"; error?: string };

export type BacktestWorkflowPanelProps = {
  onRunFinished?: () => void;
  /** Optional: list of saved runs (for parent-driven UIs). */
  runs?: string[];
  /** Optional: selected run id controlled by parent page. */
  selectedRunId?: string | null;
  /** Optional: notify parent when user picks a run in this panel. */
  onSelectRunId?: (runId: string) => void;
};

function api(path: string) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `/api${p}`;
}

const BT_PRESETS = [
  {
    id: "standard",
    label: "Standard",
    hint: "300 bars · 1h — balanced",
    ticker: "BTC/USDT",
    bars: 300,
    intervalSec: 3600,
    initialCash: 10_000,
    feeBps: 10,
  },
  {
    id: "quick",
    label: "Quick check",
    hint: "80 bars · 1h — fast",
    ticker: "BTC/USDT",
    bars: 80,
    intervalSec: 3600,
    initialCash: 10_000,
    feeBps: 10,
  },
  {
    id: "dense",
    label: "Dense",
    hint: "500 bars · 15m — more detail",
    ticker: "BTC/USDT",
    bars: 500,
    intervalSec: 900,
    initialCash: 10_000,
    feeBps: 10,
  },
] as const;

function formatBarStep(sec: number): string {
  if (sec >= 3600 && sec % 3600 === 0) return `${sec / 3600}h`;
  if (sec >= 60 && sec % 60 === 0) return `${sec / 60}m`;
  return `${sec}s`;
}

export function BacktestWorkflowPanel({ onRunFinished, selectedRunId, onSelectRunId }: BacktestWorkflowPanelProps) {
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [setupOpen, setSetupOpen] = useState(true);

  const [btTicker, setBtTicker] = useState("BTC/USDT");
  const [btBars, setBtBars] = useState(300);
  const [btIntervalSec, setBtIntervalSec] = useState(3600);
  const [btInitialCash, setBtInitialCash] = useState(10_000);
  const [btFeeBps, setBtFeeBps] = useState(10);
  const [btLoading, setBtLoading] = useState(false);
  const [bt, setBt] = useState<OpsBacktestResponse | null>(null);
  const [jobRunId, setJobRunId] = useState<string | null>(null);
  const [job, setJob] = useState<BacktestJob | null>(null);
  const [publishLoading, setPublishLoading] = useState(false);
  const [publishResult, setPublishResult] = useState<Record<string, unknown> | null>(null);
  const publishRunId = (selectedRunId ?? bt?.run_id ?? "").trim();

  const intervalChoices = useMemo(
    () =>
      [
        { sec: 60, label: "1m" },
        { sec: 300, label: "5m" },
        { sec: 900, label: "15m" },
        { sec: 3600, label: "1h" },
        { sec: 14_400, label: "4h" },
        { sec: 86_400, label: "1d" },
      ] as const,
    [],
  );

  async function runBacktest() {
    setError(null);
    setBtLoading(true);
    setBt(null);
    setJob(null);
    setJobRunId(null);
    try {
      const res = await fetch(api("/ops/backtests/quick/async"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: btTicker,
          n_bars: Number(btBars),
          interval_sec: Number(btIntervalSec),
          initial_cash: Number(btInitialCash),
          fee_bps: Number(btFeeBps),
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(
          (json as any)?.detail?.error ||
            (json as any)?.detail ||
            (json as any)?.error ||
            `Backtest failed (${res.status})`,
        );
      }
      const rid = String((json as any)?.run_id || "").trim();
      if (!rid) throw new Error("Backtest did not return a run_id");
      setJobRunId(rid);
    } catch (e: any) {
      setError(e?.message || "Backtest failed");
    } finally {
      // keep loading true while polling
    }
  }

  useEffect(() => {
    let cancelled = false;
    let t: any = null;
    async function poll() {
      if (!jobRunId) return;
      try {
        const res = await fetch(`/api/backtests/jobs/${encodeURIComponent(jobRunId)}`, { cache: "no-store" as any });
        const json = (await res.json().catch(() => ({}))) as BacktestJob;
        if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || `Poll failed (${res.status})`);
        if (cancelled) return;
        setJob(json);
        if ((json as any)?.status === "completed") {
          const out = (json as any)?.result as OpsBacktestResponse | undefined;
          if (out) setBt(out);
          if (out?.run_id) onSelectRunId?.(String(out.run_id));
          setBtLoading(false);
          onRunFinished?.();
          return;
        }
        if ((json as any)?.status === "failed") {
          setBtLoading(false);
          setError(((json as any)?.error as any) || "Backtest failed");
          return;
        }
      } catch (e: any) {
        if (!cancelled) {
          setBtLoading(false);
          setError(e?.message || "Backtest poll failed");
        }
        return;
      }
      t = setTimeout(poll, 400);
    }
    void poll();
    return () => {
      cancelled = true;
      if (t) clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobRunId]);

  async function publishBacktest() {
    setError(null);
    setPublishLoading(true);
    setPublishResult(null);
    try {
      const res = await fetch(api("/ops/publish/backtest"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: publishRunId, confirm: true }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg =
          (json as any)?.detail?.hint ||
          (json as any)?.detail?.error ||
          (json as any)?.detail ||
          (json as any)?.error ||
          `Publish failed (${res.status})`;
        throw new Error(msg);
      }
      setPublishResult(json);
      onRunFinished?.();
    } catch (e: any) {
      setError(e?.message || "Publish failed");
    } finally {
      setPublishLoading(false);
    }
  }

  useEffect(() => {
    const raw = (location.hash || "").replace(/^#/, "");
    const m = raw.match(/^receipts-(.+)$/);
    if (!m?.[1]) return;
    try {
      const id = decodeURIComponent(m[1]);
      if (id) {
        onSelectRunId?.(id);
      }
    } catch {
      /* ignore */
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.hash]);

  useEffect(() => {
    const rid = (selectedRunId ?? "").trim();
    if (!rid) return;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRunId]);

  return (
    <div className="space-y-6" id="run-backtest">
      {error ? (
        <div className="rounded-lg border border-destructive/35 bg-destructive/10 px-4 py-3 text-sm text-destructive" role="alert">
          {error}
        </div>
      ) : null}

      <Card>
        <CardHeader className="border-b">
          <Collapsible open={setupOpen} onOpenChange={setSetupOpen}>
            <CollapsibleTrigger asChild>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 text-left"
              >
                <div>
                  <CardTitle className="text-base">Backtest setup</CardTitle>
                  <CardDescription>Run a new backtest (presets + parameters).</CardDescription>
                </div>
                <ChevronDown
                  className={cn(
                    "h-4 w-4 shrink-0 text-muted-foreground transition-transform",
                    setupOpen && "rotate-180",
                  )}
                />
              </button>
            </CollapsibleTrigger>
            <CollapsibleContent>
              <CardContent className="space-y-5 pt-4">
                <div>
                  <p className="mb-2 text-xs font-medium text-muted-foreground">Preset</p>
                  <div className="grid gap-2 sm:grid-cols-3">
                    {BT_PRESETS.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => {
                          setBtTicker(p.ticker);
                          setBtBars(p.bars);
                          setBtIntervalSec(p.intervalSec);
                          setBtInitialCash(p.initialCash);
                          setBtFeeBps(p.feeBps);
                        }}
                        className="rounded-lg border border-border bg-muted/30 px-3 py-2.5 text-left transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      >
                        <div className="text-sm font-medium">{p.label}</div>
                        <div className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{p.hint}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="bt-ticker">Market</Label>
                  <Input
                    id="bt-ticker"
                    value={btTicker}
                    onChange={(e) => setBtTicker(e.target.value)}
                    className="max-w-md font-mono text-sm"
                    placeholder="BTC/USDT"
                  />
                </div>

                <div className="rounded-lg border border-dashed border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
                  <span className="text-foreground">Run summary:</span>{" "}
                  <span className="font-mono text-foreground">{btBars}</span> bars ·{" "}
                  <span className="font-mono text-foreground">{formatBarStep(btIntervalSec)}</span> steps ·{" "}
                  <span className="font-mono text-foreground">${btInitialCash}</span> cash ·{" "}
                  <span className="font-mono text-foreground">{btFeeBps}</span> bps fee
                </div>

                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="bt-bars">Bars</Label>
                    <Input
                      id="bt-bars"
                      type="number"
                      min={1}
                      value={btBars}
                      onChange={(e) => setBtBars(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Bar interval</Label>
                    <div className="grid grid-cols-3 gap-2">
                      {intervalChoices.map((c) => {
                        const active = btIntervalSec === c.sec;
                        return (
                          <button
                            key={c.sec}
                            type="button"
                            onClick={() => setBtIntervalSec(c.sec)}
                            className={cn(
                              "rounded-lg border px-2.5 py-2 text-xs font-medium transition-colors",
                              active ? "border-border bg-muted text-foreground" : "border-border bg-background hover:bg-muted/60",
                            )}
                          >
                            {c.label}
                          </button>
                        );
                      })}
                    </div>
                    <Input
                      id="bt-interval-sec"
                      type="number"
                      min={1}
                      value={btIntervalSec}
                      onChange={(e) => setBtIntervalSec(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="bt-cash">Initial cash</Label>
                    <Input
                      id="bt-cash"
                      type="number"
                      min={0}
                      value={btInitialCash}
                      onChange={(e) => setBtInitialCash(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="bt-fee">Fee (basis points)</Label>
                    <Input
                      id="bt-fee"
                      type="number"
                      min={0}
                      value={btFeeBps}
                      onChange={(e) => setBtFeeBps(Number(e.target.value))}
                    />
                  </div>
                </div>

                <Button type="button" className="w-full sm:w-auto" onClick={() => void runBacktest()} disabled={btLoading}>
                  {btLoading ? "Running (streaming)…" : "Run backtest"}
                </Button>

                {btLoading && jobRunId ? (
                  <div className="space-y-2 rounded-lg border border-border bg-muted/20 px-3 py-3 text-sm">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="text-xs text-muted-foreground">
                        run <span className="font-mono text-[11px] text-foreground">{jobRunId}</span>
                      </div>
                      <div className="text-xs text-muted-foreground">
                        {job && (job as any).status ? (job as any).status : "starting…"}
                      </div>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-background">
                      <div
                        className="h-full bg-foreground/80 transition-[width] duration-200"
                        style={{
                          width:
                            job && (job as any).total_steps
                              ? `${(Math.min(100, Math.max(0, (((job as any).step || 0) / (job as any).total_steps) * 100))).toFixed(1)}%`
                              : "10%",
                        }}
                      />
                    </div>
                    <div className="flex flex-wrap gap-3 text-[11px] text-muted-foreground">
                      <span>
                        step{" "}
                        <span className="font-mono text-foreground">{job && (job as any).step ? (job as any).step : 0}</span>
                        {job && (job as any).total_steps ? (
                          <>
                            {" "}
                            / <span className="font-mono text-foreground">{(job as any).total_steps}</span>
                          </>
                        ) : null}
                      </span>
                      <span>
                        trades <span className="font-mono text-foreground">{job && (job as any).trade_count ? (job as any).trade_count : 0}</span>
                      </span>
                      <span>
                        positions <span className="font-mono text-foreground">{job && (job as any).positions ? (job as any).positions : 0}</span>
                      </span>
                      <span>
                        equity{" "}
                        <span className="font-mono text-foreground">
                          {job && typeof (job as any).equity === "number" ? (job as any).equity.toFixed(2) : "—"}
                        </span>
                      </span>
                    </div>
                  </div>
                ) : null}
              </CardContent>
            </CollapsibleContent>
          </Collapsible>
        </CardHeader>
      </Card>

    </div>
  );
}
