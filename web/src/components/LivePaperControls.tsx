"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { useNowSec } from "@/hooks/useNowSec";
import {
  formatCountdown,
  formatIntervalLabel,
  formatUptime,
  scanProgressPct,
  secondsUntilNextScan,
} from "@/lib/paperScanClock";

type PaperStatus = {
  running?: boolean;
  ticker?: string;
  interval_sec?: number;
  started_at?: number;
  phase?: string | null;
  scan_iteration?: number;
  last_scan_started_at?: number | null;
  last_scan_finished_at?: number | null;
  next_scan_at?: number | null;
  updated_at?: number | null;
  latest_run_id?: string | null;
  paper_run_id?: string | null;
  message?: string;
  detail?: string;
  active_backtest_id?: string | null;
  desk_message?: string;
};

type PaperBook = {
  start_usdt?: number;
  cash_usdt?: number;
  free_cash_usdt?: number;
  margin_locked_usdt?: number;
  equity_usdt?: number;
  note?: string;
};

const INTERVAL_OPTIONS = [
  { sec: 300, label: "5m" },
  { sec: 900, label: "15m" },
  { sec: 1800, label: "30m" },
  { sec: 3600, label: "1h" },
] as const;

const DEFAULT_INTERVAL_SEC = 900;
const INTERVAL_STORAGE_KEY = "nexus_paper_interval_sec";

function readStoredInterval(): number {
  if (typeof window === "undefined") return DEFAULT_INTERVAL_SEC;
  try {
    const raw = window.localStorage.getItem(INTERVAL_STORAGE_KEY);
    const n = raw ? Number(raw) : NaN;
    if (INTERVAL_OPTIONS.some((o) => o.sec === n)) return n;
  } catch {
    // ignore
  }
  return DEFAULT_INTERVAL_SEC;
}

export function LivePaperControls({
  compact = false,
  onRunningChange,
}: {
  compact?: boolean;
  onRunningChange?: (running: boolean, latestRunId?: string | null) => void;
}) {
  const [status, setStatus] = useState<PaperStatus | null>(null);
  const [book, setBook] = useState<PaperBook | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ticker, setTicker] = useState("BTC/USDT");
  const [intervalSec, setIntervalSec] = useState(DEFAULT_INTERVAL_SEC);
  const [copied, setCopied] = useState(false);
  const nowSec = useNowSec(1000);

  useEffect(() => {
    setIntervalSec(readStoredInterval());
  }, []);

  const refreshBook = useCallback(async () => {
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/paper/book`, { cache: "no-store" });
      if (!res.ok) return;
      setBook((await res.json()) as PaperBook);
    } catch {
      // ignore
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/paper/status`, { cache: "no-store" });
      const data = (await res.json().catch(() => ({}))) as PaperStatus;
      if (!res.ok) {
        setErr(typeof data.detail === "string" ? data.detail : "Status failed");
        return;
      }
      setStatus(data);
      setErr(null);
      onRunningChange?.(Boolean(data.running), data.paper_run_id ?? data.latest_run_id);
      if (data.running) {
        if (data.ticker) setTicker(data.ticker);
        if (typeof data.interval_sec === "number" && data.interval_sec > 0) {
          setIntervalSec(data.interval_sec);
        }
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [onRunningChange]);

  const running = Boolean(status?.running);

  useEffect(() => {
    void refresh();
    void refreshBook();
    const ms = running ? 2000 : 4000;
    const id = window.setInterval(() => {
      void refresh();
      void refreshBook();
    }, ms);
    return () => window.clearInterval(id);
  }, [refresh, refreshBook, running]);

  const onIntervalChange = (sec: number) => {
    setIntervalSec(sec);
    try {
      window.localStorage.setItem(INTERVAL_STORAGE_KEY, String(sec));
    } catch {
      // ignore
    }
  };

  const start = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/paper/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticker, interval_sec: intervalSec }),
      });
      const data = (await res.json().catch(() => ({}))) as PaperStatus;
      if (!res.ok) {
        const detail =
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? String((data.detail as { msg?: string }[])[0]?.msg || "Start failed")
              : "Start failed";
        setErr(detail);
        return;
      }
      setStatus(data);
      onRunningChange?.(true, data.paper_run_id ?? data.latest_run_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      void refresh();
    }
  };

  const stop = async () => {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/paper/stop`, { method: "POST" });
      const data = (await res.json().catch(() => ({}))) as PaperStatus;
      if (!res.ok) {
        setErr(data.detail || "Stop failed");
        return;
      }
      setStatus(data);
      onRunningChange?.(false, data.paper_run_id ?? data.latest_run_id);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
      void refresh();
    }
  };

  const cash = typeof book?.cash_usdt === "number" ? book.cash_usdt : null;
  const startCash = typeof book?.start_usdt === "number" ? book.start_usdt : null;
  const paperRunLabel = (status?.paper_run_id ?? status?.latest_run_id ?? "").trim();
  const serverInterval =
    typeof status?.interval_sec === "number" && status.interval_sec > 0
      ? status.interval_sec
      : intervalSec;
  const scanning = (status?.phase || "").toLowerCase() === "scanning";
  const remaining = running
    ? secondsUntilNextScan({
        nowSec,
        phase: status?.phase,
        nextScanAt: status?.next_scan_at,
        intervalSec: serverInterval,
        updatedAt: status?.updated_at,
        lastScanFinishedAt: status?.last_scan_finished_at,
      })
    : null;
  const pct = scanProgressPct({
    remainingSec: remaining,
    intervalSec: serverInterval,
    phase: status?.phase,
  });

  const copyRunId = async () => {
    if (!paperRunLabel) return;
    try {
      await navigator.clipboard.writeText(paperRunLabel);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  };

  return (
    <div
      className={`border-b border-[color:var(--nexus-card-stroke)] bg-[rgba(0,212,170,0.05)] ${compact ? "px-3 py-2" : "px-4 py-2.5"}`}
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
        <span className="font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)]">
          Live
        </span>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider ${
            running
              ? "border-[rgba(0,212,170,0.35)] text-[var(--nexus-glow)]"
              : "border-[color:var(--nexus-card-stroke)] text-[var(--nexus-muted)]"
          }`}
        >
          {running ? (scanning ? "scanning" : "running") : "stopped"}
        </span>

        {!running ? (
          <>
            <input
              className="h-8 w-28 rounded-md border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 font-mono text-[10px] text-[var(--nexus-text)] outline-none focus:border-[rgba(0,212,170,0.45)]"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              disabled={busy}
              aria-label="Paper ticker"
            />
            <label className="flex h-8 items-center gap-1.5 font-mono text-[9px] text-[var(--nexus-muted)]">
              every
              <select
                className="h-8 rounded-md border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 font-mono text-[10px] text-[var(--nexus-text)] outline-none focus:border-[rgba(0,212,170,0.45)]"
                value={intervalSec}
                onChange={(e) => onIntervalChange(Number(e.target.value))}
                disabled={busy}
                aria-label="Iteration interval"
              >
                {INTERVAL_OPTIONS.map((o) => (
                  <option key={o.sec} value={o.sec}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </>
        ) : (
          <span className="font-mono text-[10px] text-[var(--nexus-muted)]">
            <span className="text-[var(--nexus-text)]">{status?.ticker}</span>
            {" · "}
            every {formatIntervalLabel(serverInterval)}
            {typeof status?.scan_iteration === "number" && status.scan_iteration > 0
              ? ` · #${status.scan_iteration}`
              : ""}
            {" · "}
            up {formatUptime(status?.started_at, nowSec)}
          </span>
        )}

        {running ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => void stop()}
            className="inline-flex h-8 items-center rounded-md border border-[rgba(248,113,113,0.35)] bg-transparent px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-[rgba(248,113,113,0.95)] outline-none transition hover:bg-[rgba(248,113,113,0.10)] disabled:opacity-40"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            disabled={busy}
            onClick={() => void start()}
            title="Start live paper session (Research can run in parallel)"
            className="inline-flex h-8 items-center rounded-md bg-[var(--nexus-glow)] px-3 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--nexus-bg)] outline-none transition hover:brightness-110 disabled:opacity-40"
          >
            Start session
          </button>
        )}

        {typeof book?.equity_usdt === "number" ? (
          <span
            className="font-mono text-[9px] text-[var(--nexus-muted)]"
            title={book?.note || "Book equity = free cash + margin locked"}
          >
            ${book.equity_usdt.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            {cash != null
              ? ` · free $${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
              : ""}
          </span>
        ) : cash != null ? (
          <span className="font-mono text-[9px] text-[var(--nexus-muted)]">
            ${cash.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </span>
        ) : null}

        <Link
          href="/console?view=portfolio"
          className="font-mono text-[10px] text-[var(--nexus-muted)] underline-offset-2 hover:text-[var(--nexus-text)] hover:underline"
        >
          Portfolio
        </Link>

        {running ? (
          <div className="ml-auto flex min-w-[9.5rem] max-w-xs flex-1 items-center gap-2 sm:flex-none">
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <span className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                  {scanning ? "Scan" : "Next"}
                </span>
                <span
                  className={`font-mono text-[12px] tabular-nums ${
                    scanning ? "animate-pulse text-[var(--nexus-glow)]" : "text-[var(--nexus-text)]"
                  }`}
                >
                  {scanning
                    ? "…"
                    : remaining != null
                      ? formatCountdown(remaining)
                      : "—"}
                </span>
              </div>
              <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-[var(--nexus-surface)]">
                <div
                  className="h-full bg-[var(--nexus-glow)]/60 transition-[width] duration-500"
                  style={{ width: `${scanning ? 100 : pct}%` }}
                />
              </div>
            </div>
          </div>
        ) : null}

        {err ? (
          <span className="w-full font-mono text-[10px] text-[rgba(248,113,113,0.95)]">{err}</span>
        ) : null}
      </div>

      {running && paperRunLabel ? (
        <div className="mt-1.5 flex min-w-0 items-center gap-2">
          <span className="shrink-0 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
            Run
          </span>
          <button
            type="button"
            onClick={() => void copyRunId()}
            title="Click to copy full run id"
            className="min-w-0 flex-1 text-left font-mono text-[10px] text-[var(--nexus-text)] hover:text-[var(--nexus-glow)]"
          >
            <span className="break-all">{paperRunLabel}</span>
            <span className="ml-1.5 text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
              {copied ? "copied" : "copy"}
            </span>
          </button>
        </div>
      ) : null}
    </div>
  );
}
