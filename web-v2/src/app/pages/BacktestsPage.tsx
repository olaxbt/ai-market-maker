import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { Activity, ChevronDown, MessageSquareText, RefreshCcw, UploadCloud } from "lucide-react";

import { BacktestWorkflowPanel } from "../components/BacktestWorkflowPanel";
import { BacktestResultsPanel } from "../components/BacktestResultsPanel";
import { Popover, PopoverContent, PopoverTrigger } from "../components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "../components/ui/command";

type BacktestsIndex = {
  runs?: string[];
};

function fmtTsFromRunId(runId: string) {
  const m = runId.match(/(\d{9,})/);
  if (!m) return "—";
  const sec = Number(m[1]);
  if (!Number.isFinite(sec)) return "—";
  return new Date(sec * 1000).toLocaleString();
}

export default function BacktestsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [runs, setRuns] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runPickerOpen, setRunPickerOpen] = useState(false);
  const [publishLoading, setPublishLoading] = useState(false);
  const [publishMsg, setPublishMsg] = useState<string | null>(null);

  const selectedFromHash = useMemo(() => {
    const raw = (location.hash || "").replace(/^#/, "");
    const m = raw.match(/^(?:run|receipts)-(.+)$/);
    if (!m?.[1]) return null;
    try {
      const id = decodeURIComponent(m[1]);
      return id || null;
    } catch {
      return null;
    }
  }, [location.hash]);

  /** e.g. `/backtests?run=bt-…` from Studio / inline widget (hash `#run-…` is the canonical form). */
  const selectedFromQuery = useMemo(() => {
    try {
      const q = new URLSearchParams(location.search || "");
      const r = (q.get("run") || "").trim();
      return r || null;
    } catch {
      return null;
    }
  }, [location.search]);

  const deepLinkedRunId = useMemo(() => selectedFromHash || selectedFromQuery, [selectedFromHash, selectedFromQuery]);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/backtests", { cache: "no-store" as any });
      const json = (await res.json().catch(() => ({}))) as BacktestsIndex;
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || `Failed to load backtests (${res.status})`);
      const nextRuns = Array.isArray(json?.runs) ? json.runs : [];
      setRuns(nextRuns);
    } catch (e: any) {
      setError(e?.message || "Failed to load backtests");
      setRuns([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    // Keep selected run in sync with URL: `#run-…` (preferred) or legacy `?run=…`.
    if (deepLinkedRunId) {
      setSelectedRunId(deepLinkedRunId);
      if (selectedFromQuery && !selectedFromHash) {
        navigate(`/backtests#run-${encodeURIComponent(deepLinkedRunId)}`, { replace: true });
      }
      return;
    }
    // No deep-link: auto-select the newest run if we have one.
    if (!selectedRunId && runs.length > 0) {
      const newest = runs[0];
      setSelectedRunId(newest);
      navigate(`/backtests#run-${encodeURIComponent(newest)}`, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runs, deepLinkedRunId, selectedFromQuery, selectedFromHash]);

  function selectRun(rid: string) {
    const id = (rid || "").trim();
    if (!id) return;
    setSelectedRunId(id);
    navigate(`/backtests#run-${encodeURIComponent(id)}`, { replace: false });
  }

  async function publishSelected() {
    const rid = (selectedRunId ?? "").trim();
    if (!rid || publishLoading) return;
    setPublishLoading(true);
    setPublishMsg(null);
    try {
      const res = await fetch("/api/ops/publish/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: rid, confirm: true }),
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
      const provider = (json as any)?.provider;
      const run_id = (json as any)?.run_id;
      const inserted = Boolean((json as any)?.inserted);
      setPublishMsg(
        provider && run_id
          ? `Published ${provider}/${run_id} (${inserted ? "inserted" : "already present"}).`
          : "Published.",
      );
    } catch (e: any) {
      setPublishMsg(e?.message || "Publish failed");
    } finally {
      setPublishLoading(false);
    }
  }

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Backtests</p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">Runs & workflow</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                Run local backtests, publish results, and inspect receipts. Includes presets and a saved runs list.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl space-y-6">
          {error ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          ) : null}

          <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
            <BacktestWorkflowPanel
              onRunFinished={() => void load()}
              runs={runs}
              selectedRunId={selectedRunId}
              onSelectRunId={selectRun}
            />

            <div className="space-y-6">
              <BacktestResultsPanel runId={selectedRunId} />

              <div className="flex flex-wrap items-center gap-2">
                <Popover open={runPickerOpen} onOpenChange={setRunPickerOpen}>
                  <PopoverTrigger asChild>
                    <button
                      type="button"
                      className="inline-flex min-w-[260px] flex-1 items-center justify-between gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70"
                      title="Select a saved run"
                    >
                      <span className="min-w-0 truncate">
                        {selectedRunId ? (
                          <span className="font-mono text-xs font-semibold">{selectedRunId}</span>
                        ) : loading ? (
                          "Loading runs…"
                        ) : runs.length === 0 ? (
                          "No saved runs"
                        ) : (
                          "Select a run…"
                        )}
                      </span>
                      <span className="inline-flex items-center gap-2 text-[11px] text-muted-foreground">
                        {runs.length ? `${runs.length}` : ""}
                        <ChevronDown className="h-4 w-4 opacity-70" />
                      </span>
                    </button>
                  </PopoverTrigger>
                  <PopoverContent className="w-[360px] p-0" align="start">
                    <Command>
                      <CommandInput placeholder="Search runs…" />
                      <CommandList>
                        <CommandEmpty>No runs found.</CommandEmpty>
                        <CommandGroup heading="Saved runs">
                          {runs.slice(0, 300).map((rid) => (
                            <CommandItem
                              key={rid}
                              value={rid}
                              onSelect={() => {
                                selectRun(rid);
                                setRunPickerOpen(false);
                              }}
                            >
                              <div className="flex w-full items-center justify-between gap-3">
                                <span className="min-w-0 truncate font-mono text-[12px]">{rid}</span>
                                <span className="shrink-0 text-[10px] text-muted-foreground">{fmtTsFromRunId(rid)}</span>
                              </div>
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      </CommandList>
                    </Command>
                  </PopoverContent>
                </Popover>

                <button
                  type="button"
                  onClick={() => void load()}
                  className="inline-flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70"
                  title="Refresh saved runs list"
                >
                  <RefreshCcw className="h-3.5 w-3.5" />
                  Refresh
                </button>

                {selectedRunId ? (
                  <>
                    <button
                      type="button"
                      onClick={() => void publishSelected()}
                      disabled={publishLoading}
                      className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70 disabled:opacity-50"
                      title="Publish selected run to leaderboard"
                    >
                      <UploadCloud className="h-3.5 w-3.5" />
                      {publishLoading ? "Publishing…" : "Publish"}
                    </button>
                    <Link
                      to={`/studio?run=${encodeURIComponent(selectedRunId)}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70"
                      title="Ask about this run in Studio"
                    >
                      <MessageSquareText className="h-3.5 w-3.5" />
                      Ask
                    </Link>
                    <Link
                      to={`/console?view=monitor&run=${encodeURIComponent(selectedRunId)}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70"
                      title="Monitor replay"
                    >
                      <Activity className="h-3.5 w-3.5" />
                      Monitor
                    </Link>
                  </>
                ) : null}
              </div>

              {publishMsg ? (
                <div
                  className={[
                    "rounded-lg border px-3 py-2 text-sm",
                    publishMsg.toLowerCase().includes("publish failed") || publishMsg.toLowerCase().includes("failed")
                      ? "border-destructive/35 bg-destructive/10 text-destructive"
                      : "border-emerald-500/25 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
                  ].join(" ")}
                >
                  {publishMsg}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
