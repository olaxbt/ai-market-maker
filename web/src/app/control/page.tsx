"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

function flowOrigin(): string {
  const raw = process.env.NEXT_PUBLIC_FLOW_API_BASE_URL?.trim() || "http://127.0.0.1:8001";
  return raw.replace(/\/$/, "");
}

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

type OpsBacktestResponse = {
  run_id?: string;
  trade_count?: number;
  metrics?: Record<string, unknown>;
  paths?: Record<string, unknown>;
  evaluation?: Record<string, unknown>;
};

type RuntimeSettings = {
  path?: string;
  settings?: Record<string, any>;
};

type IterationRow = {
  ts?: number;
  run_id?: string;
  symbol?: string;
  backtest?: { cash?: number; positions?: Record<string, unknown>; window_len?: number; window_last_ts_ms?: number };
  memory?: { recent_views?: unknown[]; recent_decisions?: unknown[]; recent_tool_events?: unknown[] };
  decision?: { stance?: string | null; confidence?: number };
  error?: string;
};

function Pill({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-lg border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.35)] px-2 py-1 text-[10px] text-[rgba(226,232,240,0.85)]">
      {children}
    </span>
  );
}

export default function ControlCenterPage() {
  const base = useMemo(() => flowOrigin(), []);

  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [selftest, setSelftest] = useState<Selftest | null>(null);
  const [rt, setRt] = useState<RuntimeSettings | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [btTicker, setBtTicker] = useState("BTC/USDT");
  const [btBars, setBtBars] = useState(300);
  const [btIntervalSec, setBtIntervalSec] = useState(3600);
  const [btInitialCash, setBtInitialCash] = useState(1000);
  const [btFeeBps, setBtFeeBps] = useState(10);
  const [btLoading, setBtLoading] = useState(false);
  const [bt, setBt] = useState<OpsBacktestResponse | null>(null);

  const [publishRunId, setPublishRunId] = useState("");
  const [publishLoading, setPublishLoading] = useState(false);
  const [publishResult, setPublishResult] = useState<{ ok?: boolean; inserted?: boolean; provider?: string; run_id?: string } | null>(null);

  const [receiptsRunId, setReceiptsRunId] = useState("");
  const [receiptsLoading, setReceiptsLoading] = useState(false);
  const [receipts, setReceipts] = useState<IterationRow[] | null>(null);

  const hm = (rt?.settings?.harness_memory ?? {}) as Record<string, any>;
  const [hmViews, setHmViews] = useState<number>(60);
  const [hmDecisions, setHmDecisions] = useState<number>(60);
  const [hmTools, setHmTools] = useState<number>(60);
  const [hmSaving, setHmSaving] = useState(false);

  function refresh() {
    setError(null);
    Promise.all([
      fetch(`${base}/capabilities`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${base}/ops/selftest`, { cache: "no-store" }).then((r) => r.json()),
      fetch(`${base}/runtime-settings`, { cache: "no-store" }).then((r) => r.json()),
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

  async function runBacktest() {
    setError(null);
    setBtLoading(true);
    setBt(null);
    setPublishResult(null);
    try {
      const res = await fetch(`${base}/ops/backtests/quick`, {
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
        throw new Error(json?.detail?.error || json?.detail || json?.error || `Backtest failed (${res.status})`);
      }
      setBt(json);
      if (json?.run_id) setPublishRunId(String(json.run_id));
    } catch (e: any) {
      setError(e?.message || "Backtest failed");
    } finally {
      setBtLoading(false);
    }
  }

  async function publishBacktest() {
    setError(null);
    setPublishLoading(true);
    setPublishResult(null);
    try {
      const res = await fetch(`${base}/ops/publish/backtest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ run_id: publishRunId, confirm: true }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        const msg = json?.detail?.hint || json?.detail?.error || json?.detail || json?.error || `Publish failed (${res.status})`;
        throw new Error(msg);
      }
      setPublishResult(json);
    } catch (e: any) {
      setError(e?.message || "Publish failed");
    } finally {
      setPublishLoading(false);
    }
  }

  async function loadReceipts(runId: string) {
    const rid = (runId || "").trim();
    if (!rid) return;
    setError(null);
    setReceiptsLoading(true);
    setReceipts(null);
    try {
      const res = await fetch(`${base}/backtests/${encodeURIComponent(rid)}/iterations?limit=300`, { cache: "no-store" });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(json?.detail || json?.error || `Failed to load receipts (${res.status})`);
      }
      setReceipts(Array.isArray(json?.iterations) ? json.iterations : []);
    } catch (e: any) {
      setError(e?.message || "Failed to load receipts");
    } finally {
      setReceiptsLoading(false);
    }
  }

  async function saveHarnessMemory() {
    setError(null);
    setHmSaving(true);
    try {
      const res = await fetch(`${base}/runtime-settings/harness-memory`, {
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
        throw new Error(json?.detail || json?.error || `Failed to save harness memory (${res.status})`);
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
    <div className="nexus-bg min-h-screen">
      <NexusSectionHeader title="CONTROL" subtitle="Setup • Operate • Observe (operator console)." active="nexus" />
      <div className="mx-auto w-full max-w-5xl px-6 py-10">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-[11px] uppercase tracking-[0.18em] text-[rgba(138,149,166,0.55)]">Control Center</div>
          <h1 className="mt-1 text-[18px] font-semibold text-[rgba(226,232,240,0.95)]">Setup • Operate • Observe</h1>
          <div className="mt-1 text-[11px] text-[rgba(138,149,166,0.6)]">
            Flow API <code>{base}</code>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Pill>mode: {modeHint}</Pill>
          <button
            type="button"
            onClick={refresh}
            className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.22)]"
          >
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-[rgba(242,92,84,0.25)] bg-[rgba(242,92,84,0.08)] px-4 py-3 text-[11px] text-[rgba(242,92,84,0.95)]">
          {error}
        </div>
      )}

      <div className="mt-6 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Setup</div>
            <Pill>{selfOk ? "healthy" : "needs attention"}</Pill>
          </div>
          <div className="mt-3 space-y-2 text-[11px] text-[rgba(138,149,166,0.75)]">
            <div className="flex items-center justify-between gap-3">
              <span>Runs dir writable</span>
              <code className="text-[rgba(226,232,240,0.82)]">{selftest?.runs?.ok ? "ok" : "fail"}</code>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Database configured</span>
              <code className="text-[rgba(226,232,240,0.82)]">{selftest?.db?.configured ? "yes" : "no"}</code>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Database connectivity</span>
              <code className="text-[rgba(226,232,240,0.82)]">{selftest?.db?.ok ? "ok" : selftest?.db?.configured ? "fail" : "n/a"}</code>
            </div>
            {selftest?.runs?.error ? <div className="text-[rgba(242,92,84,0.9)]">{selftest.runs.error}</div> : null}
            {selftest?.db?.error ? <div className="text-[rgba(242,92,84,0.9)]">{selftest.db.error}</div> : null}
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Link
              href="/get-started"
              className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.22)]"
            >
              Clone + run
            </Link>
            <Link
              href="/console?view=research"
              className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.22)]"
            >
              Open Research
            </Link>
            <Link
              href="/tools"
              className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.22)]"
            >
              Browse tools
            </Link>
          </div>
        </div>

        <div className="rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Capabilities</div>
            <Pill>ops: {caps?.ops?.can_run_backtests ? "on" : "off"}</Pill>
          </div>
          <div className="mt-3 space-y-2 text-[11px] text-[rgba(138,149,166,0.75)]">
            <div className="flex items-center justify-between gap-3">
              <span>External submit requires key</span>
              <code className="text-[rgba(226,232,240,0.82)]">{caps?.leaderboard?.external_submit_requires_key ? "yes" : "no"}</code>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>External submit requires signature</span>
              <code className="text-[rgba(226,232,240,0.82)]">{caps?.leaderboard?.external_submit_requires_signature ? "yes" : "no"}</code>
            </div>
            <div className="flex items-center justify-between gap-3">
              <span>Provider keys configured</span>
              <code className="text-[rgba(226,232,240,0.82)]">{caps?.leaderboard?.provider_keys_configured ? "yes" : "no"}</code>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <div className="rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
          <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Operate: run a backtest</div>
          <div className="mt-3 grid gap-2 md:grid-cols-2">
            <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
              Ticker
              <input
                value={btTicker}
                onChange={(e) => setBtTicker(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
              Bars
              <input
                value={btBars}
                type="number"
                onChange={(e) => setBtBars(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
              Interval (sec)
              <input
                value={btIntervalSec}
                type="number"
                onChange={(e) => setBtIntervalSec(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
              Initial cash
              <input
                value={btInitialCash}
                type="number"
                onChange={(e) => setBtInitialCash(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
              Fee (bps)
              <input
                value={btFeeBps}
                type="number"
                onChange={(e) => setBtFeeBps(Number(e.target.value))}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <div className="flex items-end">
              <button
                type="button"
                onClick={runBacktest}
                disabled={btLoading}
                className="w-full rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)] disabled:opacity-60"
              >
                {btLoading ? "Running…" : "Run backtest"}
              </button>
            </div>
          </div>

          {bt?.run_id ? (
            <div className="mt-4 rounded-xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.25)] px-4 py-3 text-[11px] text-[rgba(138,149,166,0.8)]">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  Run: <code className="text-[rgba(226,232,240,0.92)]">{bt.run_id}</code>
                </div>
                <Link href="/leaderboard" className="text-[rgba(0,212,170,0.92)] hover:underline">
                  View leaderboard
                </Link>
              </div>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div>
                  Trades: <code className="text-[rgba(226,232,240,0.88)]">{String(bt.trade_count ?? "")}</code>
                </div>
                <div>
                  Sharpe:{" "}
                  <code className="text-[rgba(226,232,240,0.88)]">{String((bt.metrics as any)?.sharpe ?? (bt.metrics as any)?.sharpe_ratio ?? "")}</code>
                </div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
          <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Operate: publish a backtest</div>
          <div className="mt-2 text-[11px] text-[rgba(138,149,166,0.7)]">
            Publishes <code>.runs/backtests/&lt;run_id&gt;/summary.json</code> into the leaderboard database as provider <code>local</code>.
          </div>

          <div className="mt-3 flex items-end gap-2">
            <label className="w-full text-[10px] text-[rgba(138,149,166,0.7)]">
              Run ID
              <input
                value={publishRunId}
                onChange={(e) => setPublishRunId(e.target.value)}
                className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
              />
            </label>
            <button
              type="button"
              onClick={publishBacktest}
              disabled={publishLoading || !publishRunId.trim()}
              className="shrink-0 rounded-xl border border-[rgba(99,102,241,0.18)] bg-[rgba(99,102,241,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(99,102,241,0.92)] hover:border-[rgba(99,102,241,0.28)] disabled:opacity-60"
            >
              {publishLoading ? "Publishing…" : "Publish"}
            </button>
          </div>

          {publishResult?.ok ? (
            <div className="mt-4 rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.07)] px-4 py-3 text-[11px] text-[rgba(0,212,170,0.92)]">
              Published: <code>{publishResult.provider}</code>/<code>{publishResult.run_id}</code>{" "}
              <span className="text-[rgba(138,149,166,0.75)]">(inserted: {publishResult.inserted ? "yes" : "no"})</span>
            </div>
          ) : null}

          <div className="mt-4 rounded-xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.25)] px-4 py-3 text-[11px] text-[rgba(138,149,166,0.75)]">
            Next: use <Link className="text-[rgba(0,212,170,0.92)] hover:underline" href="/leaderboard">Leaderboard</Link> to see published results,
            then <Link className="text-[rgba(0,212,170,0.92)] hover:underline" href="/console?view=research">Research</Link> to iterate strategy + policy.
          </div>
        </div>
      </div>

      <div className="mt-3 rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Tuning: harness memory (receipts)</div>
            <div className="mt-1 text-[11px] text-[rgba(138,149,166,0.7)]">
              These limits control how much recent context is included in receipts (cost + readability). Stored in{" "}
              <code>config/runtime_settings.json</code>.
            </div>
          </div>
          <Pill>{rt?.path ? "runtime-settings" : "n/a"}</Pill>
        </div>

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
            recent_views_max
            <input
              value={hmViews}
              type="number"
              onChange={(e) => setHmViews(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
            />
          </label>
          <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
            recent_decisions_max
            <input
              value={hmDecisions}
              type="number"
              onChange={(e) => setHmDecisions(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
            />
          </label>
          <label className="text-[10px] text-[rgba(138,149,166,0.7)]">
            recent_tool_events_max
            <input
              value={hmTools}
              type="number"
              onChange={(e) => setHmTools(Number(e.target.value))}
              className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none"
            />
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={saveHarnessMemory}
            disabled={hmSaving}
            className="rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)] disabled:opacity-60"
          >
            {hmSaving ? "Saving…" : "Save"}
          </button>
          <button
            type="button"
            onClick={() => {
              setHmViews(60);
              setHmDecisions(60);
              setHmTools(60);
            }}
            className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.30)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.9)] hover:border-[rgba(0,212,170,0.22)]"
          >
            Reset to defaults
          </button>
        </div>
      </div>

      <div className="mt-3 rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">Observe: run receipts (iterations)</div>
            <div className="mt-1 text-[11px] text-[rgba(138,149,166,0.7)]">
              What the system <span className="text-[rgba(226,232,240,0.85)]">saw</span>, what it{" "}
              <span className="text-[rgba(226,232,240,0.85)]">decided</span>, and any{" "}
              <span className="text-[rgba(226,232,240,0.85)]">errors</span> per bar.
            </div>
          </div>
          <Pill>{receipts ? `${receipts.length} rows` : "not loaded"}</Pill>
        </div>

        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="min-w-[320px] flex-1 text-[10px] text-[rgba(138,149,166,0.7)]">
            Backtest run_id
            <input
              value={receiptsRunId}
              onChange={(e) => setReceiptsRunId(e.target.value)}
              placeholder="e.g. bt_1778077488"
              className="mt-1 w-full rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-white outline-none placeholder:text-[rgba(138,149,166,0.45)]"
            />
          </label>
          <button
            type="button"
            onClick={() => loadReceipts(receiptsRunId)}
            disabled={receiptsLoading || !receiptsRunId.trim()}
            className="rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)] disabled:opacity-60"
          >
            {receiptsLoading ? "Loading…" : "Load receipts"}
          </button>
          <button
            type="button"
            onClick={() => {
              const rid = publishRunId.trim();
              if (rid) {
                setReceiptsRunId(rid);
                loadReceipts(rid);
              }
            }}
            disabled={!publishRunId.trim()}
            className="rounded-xl border border-[rgba(99,102,241,0.18)] bg-[rgba(99,102,241,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(99,102,241,0.92)] hover:border-[rgba(99,102,241,0.28)] disabled:opacity-60"
          >
            Use last run
          </button>
        </div>

        {receipts ? (
          <div className="mt-4 space-y-2">
            {receipts.slice(-25).map((r, idx) => {
              const stance = r?.decision?.stance ?? "";
              const conf = typeof r?.decision?.confidence === "number" ? r.decision.confidence : null;
              const hasErr = Boolean(r?.error);
              const viewsLen = Array.isArray(r?.memory?.recent_views) ? r.memory?.recent_views?.length : null;
              const decLen = Array.isArray(r?.memory?.recent_decisions) ? r.memory?.recent_decisions?.length : null;
              const toolsLen = Array.isArray(r?.memory?.recent_tool_events) ? r.memory?.recent_tool_events?.length : null;
              return (
                <div
                  key={`${idx}-${r?.ts ?? ""}`}
                  className={`rounded-xl border px-4 py-3 ${
                    hasErr
                      ? "border-[rgba(242,92,84,0.25)] bg-[rgba(242,92,84,0.06)]"
                      : "border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)]"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="text-[11px] text-[rgba(226,232,240,0.9)]">
                      <span className="text-[rgba(138,149,166,0.65)]">symbol</span> <code>{String(r?.symbol ?? "")}</code>
                      <span className="mx-2 text-[rgba(138,149,166,0.35)]">•</span>
                      <span className="text-[rgba(138,149,166,0.65)]">decision</span> <code>{stance || "n/a"}</code>
                      {conf !== null ? (
                        <>
                          <span className="mx-2 text-[rgba(138,149,166,0.35)]">•</span>
                          <span className="text-[rgba(138,149,166,0.65)]">confidence</span> <code>{conf.toFixed(3)}</code>
                        </>
                      ) : null}
                    </div>
                    <div className="flex flex-wrap items-center gap-2 text-[10px] text-[rgba(138,149,166,0.7)]">
                      <span>
                        mem: <code>views={viewsLen ?? "?"}</code> <code>decisions={decLen ?? "?"}</code>{" "}
                        <code>tools={toolsLen ?? "?"}</code>
                      </span>
                      {hasErr ? <Pill>error</Pill> : <Pill>ok</Pill>}
                    </div>
                  </div>
                  {hasErr ? (
                    <div className="mt-2 text-[11px] text-[rgba(242,92,84,0.92)]">{String(r?.error ?? "")}</div>
                  ) : null}
                </div>
              );
            })}
            {receipts.length === 0 ? (
              <div className="rounded-xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.20)] px-4 py-10 text-center text-[11px] text-[rgba(138,149,166,0.6)]">
                No receipts found for this run.
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
      </div>
    </div>
  );
}

