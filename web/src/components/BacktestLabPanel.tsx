"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { BacktestBarTimeline } from "@/components/backtest/BacktestBarTimeline";
import {
  EmbeddedBacktestChrome,
  type EmbeddedWorkspaceTab,
} from "@/components/backtest/EmbeddedBacktestChrome";
import { BacktestEquityChart } from "@/components/backtest/BacktestEquityChart";
import { BacktestTradesTable } from "@/components/backtest/BacktestTradesTable";
import { copyText } from "@/components/backtest/embeddedBacktestUtils";
import { BacktestPriceChart } from "@/features/backtest/components/BacktestPriceChart";
import { format, parseISO } from "date-fns";
import { createPortal } from "react-dom";
import ReactDatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {
  amountUnitToIntervalSec,
  BAR_INTERVAL_UNIT_LABEL,
  formatIntervalHuman,
  intervalSecToAmountUnit,
  type BarIntervalUnit,
} from "@/lib/backtestInterval";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import type { NexusPayload } from "@/types/nexus-payload";
import type {
  BacktestRunResult,
  BarsResponse,
  EquitySeriesResponse,
  OhlcvBar,
  SummaryPayload,
  TradeRow,
  TradesResponse,
} from "@/types/backtest";

type StrategyRow = {
  id: string;
  title: string;
  description: string;
  defaults: {
    n_bars: number;
    interval_sec: number;
    max_steps: number;
    fee_bps: number;
    initial_cash: number;
  };
};

type BacktestJob = {
  status: "queued" | "running" | "completed" | "failed";
  step?: number;
  total_steps?: number;
  trade_count?: number;
  equity?: number;
  vetoed?: boolean;
  error?: string;
  result?: BacktestRunResult;
};

function isIsoDate(iso: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(iso.trim());
}

function isoToDate(iso: string): Date | null {
  const t = iso.trim();
  if (!isIsoDate(t)) return null;
  try {
    const d = parseISO(t);
    return Number.isFinite(d.getTime()) ? d : null;
  } catch {
    return null;
  }
}

function dateToIso(d: Date): string {
  return format(d, "yyyy-MM-dd");
}

function DatePickerField({
  label,
  value,
  onChange,
  disabled,
  minIso,
  className,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (nextIso: string) => void;
  disabled: boolean;
  minIso?: string;
  className: string;
  /** Shown when visible label exists above the field (avoids duplicating the title in the input). */
  placeholder?: string;
}) {
  const selected = useMemo(() => isoToDate(value), [value]);
  const minDate = useMemo(() => (minIso ? isoToDate(minIso) : null), [minIso]);

  return (
    <div className="relative">
      <label className="sr-only">{label}</label>
      <ReactDatePicker
        selected={selected}
        onChange={(d: Date | null) => {
          if (!d) {
            onChange("");
            return;
          }
          onChange(dateToIso(d));
        }}
        minDate={minDate ?? undefined}
        disabled={disabled}
        dateFormat="yyyy-MM-dd"
        showMonthDropdown
        showYearDropdown
        dropdownMode="select"
        placeholderText={placeholder ?? label}
        popperPlacement="bottom-start"
        popperContainer={({ children }) => createPortal(children, document.body)}
        popperClassName="z-[1000]"
        calendarClassName="nexus-datepicker"
        className={`${className} text-left`}
      />
    </div>
  );
}

function downloadJson(data: unknown, filename: string) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}

type BacktestKpiRow = {
  totalReturnPct: number;
  sharpe: number;
  maxDrawdownPct: number;
  winRatePct: number | null;
  profitFactor: number | null;
  trades: number;
  steps: number;
};

function shortBacktestRunLabel(id: string): string {
  const t = id.trim();
  if (t.length <= 20) return t;
  return `${t.slice(0, 5)}…${t.slice(-10)}`;
}

function BacktestKpiGrid({ kpis, compact }: { kpis: BacktestKpiRow; compact?: boolean }) {
  const ddLabel =
    kpis.maxDrawdownPct > 0 && kpis.maxDrawdownPct < 0.01 ? "<0.01%" : `${kpis.maxDrawdownPct.toFixed(2)}%`;
  const winRateLabel = kpis.winRatePct == null ? "—" : `${kpis.winRatePct.toFixed(1)}%`;
  const items: { label: string; value: string; tone: string }[] = [
    {
      label: "Total return",
      value: `${kpis.totalReturnPct >= 0 ? "+" : ""}${kpis.totalReturnPct.toFixed(2)}%`,
      tone: kpis.totalReturnPct >= 0 ? "text-[var(--nexus-success)]" : "text-[var(--nexus-danger)]",
    },
    { label: "Sharpe (ann.)", value: kpis.sharpe.toFixed(3), tone: "text-[var(--nexus-text)]" },
    { label: "Max drawdown", value: ddLabel, tone: "text-[var(--nexus-danger)]/90" },
    {
      label: "Win rate",
      value: winRateLabel,
      tone: kpis.winRatePct == null ? "text-[var(--nexus-muted)]" : "text-[var(--nexus-muted)]",
    },
    { label: "Fills", value: String(kpis.trades), tone: "text-[var(--nexus-text)]" },
    { label: "Steps", value: String(kpis.steps), tone: "text-[var(--nexus-muted)]" },
  ];
  if (compact) {
    return (
      <div className="grid grid-cols-3 gap-1 sm:grid-cols-6">
        {items.map((k) => (
          <div
            key={k.label}
            className="rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/45 px-1.5 py-1"
          >
            <p className="font-mono text-[7px] uppercase leading-tight tracking-wider text-[var(--nexus-muted)]">{k.label}</p>
            <p className={`mt-0.5 truncate font-mono text-xs tabular-nums leading-tight ${k.tone}`}>{k.value}</p>
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      {items.map((k) => (
        <div
          key={k.label}
          className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/60 px-4 py-3"
        >
          <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">{k.label}</p>
          <p className={`mt-1 font-mono text-lg tabular-nums ${k.tone}`}>{k.value}</p>
        </div>
      ))}
    </div>
  );
}

export function BacktestLabPanel({
  embedded = false,
  initialRunId = null,
  embeddedView = "backtest",
}: {
  embedded?: boolean;
  initialRunId?: string | null;
  /** When embedded, preserve the host view when updating the URL. */
  embeddedView?: "backtest" | "research";
}) {
  const LIVE_RUN_STORAGE_KEY = "nexus_backtest_live_run_id";
  const router = useRouter();

  const [embeddedTab, setEmbeddedTab] = useState<EmbeddedWorkspaceTab>("saved");

  const [strategies, setStrategies] = useState<StrategyRow[]>([]);
  const [presetId, setPresetId] = useState("macd_risk_v1");
  const [ticker, setTicker] = useState("BTC/USDT");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [runPayload, setRunPayload] = useState<BacktestRunResult | null>(null);
  const [summaryPayload, setSummaryPayload] = useState<SummaryPayload | null>(null);
  const [equitySeries, setEquitySeries] = useState<EquitySeriesResponse | null>(null);
  const [tradesData, setTradesData] = useState<TradesResponse | null>(null);
  const [barsData, setBarsData] = useState<BarsResponse | null>(null);
  const [tracePayload, setTracePayload] = useState<NexusPayload | null>(null);

  const [runList, setRunList] = useState<string[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState("");
  const [jobState, setJobState] = useState<BacktestJob | null>(null);
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);

  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [nBars, setNBars] = useState("");
  const [intervalAmount, setIntervalAmount] = useState("");
  const [intervalUnit, setIntervalUnit] = useState<BarIntervalUnit>("min");
  const [maxSteps, setMaxSteps] = useState("");
  const [feeBps, setFeeBps] = useState("");
  const [initialCash, setInitialCash] = useState("");
  const [sinceIso, setSinceIso] = useState("");
  const [untilIso, setUntilIso] = useState("");
  const [windowMode, setWindowMode] = useState<"latest" | "range">("range");

  const [historyLoading, setHistoryLoading] = useState(false);

  const lastUrlRunRef = useRef<string | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const existing = window.localStorage.getItem(LIVE_RUN_STORAGE_KEY);
    if (!existing) return;
    // If the app reloads mid-run, resume polling.
    setLiveRunId(existing);
    setPollingJobId(existing);
    setJobState({ status: "queued", step: 0, total_steps: 0 });
  }, []);

  useEffect(() => {
    fetch("/api/strategies")
      .then((r) => r.json())
      .then((d: { strategies?: StrategyRow[] }) => {
        if (Array.isArray(d.strategies) && d.strategies.length) {
          setStrategies(d.strategies);
          setPresetId(d.strategies[0].id);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    const base = getFlowApiOrigin();
    fetch(`${base}/backtests`)
      .then((r) => r.json())
      .then((d: { runs?: string[] }) => {
        if (Array.isArray(d.runs)) setRunList(d.runs);
      })
      .catch(() => {});
  }, []);

  const selected = strategies.find((s) => s.id === presetId);

  useEffect(() => {
    if (!selected) return;
    setNBars(String(selected.defaults.n_bars));
    const iu = intervalSecToAmountUnit(selected.defaults.interval_sec);
    setIntervalAmount(iu.amount);
    setIntervalUnit(iu.unit);
    setMaxSteps(String(selected.defaults.max_steps));
    setFeeBps(String(selected.defaults.fee_bps));
    setInitialCash(String(selected.defaults.initial_cash));
  }, [presetId, selected]);

  const buildBody = useCallback(() => {
    const body: Record<string, unknown> = {
      preset_id: presetId,
      ticker,
      exchange_id: "binance",
    };
    if (!selected) return body;
    const nb = parseInt(nBars, 10);
    const amt = parseFloat(intervalAmount);
    const ms = parseInt(maxSteps, 10);
    if (!Number.isNaN(nb)) body.n_bars = nb;
    if (!Number.isNaN(amt) && amt > 0) body.interval_sec = amountUnitToIntervalSec(amt, intervalUnit);
    if (!Number.isNaN(ms)) body.max_steps = ms;
    if (advancedOpen) {
      const fee = parseFloat(feeBps);
      const cash = parseFloat(initialCash);
      if (!Number.isNaN(fee)) body.fee_bps = fee;
      if (!Number.isNaN(cash)) body.initial_cash = cash;
    }

    const s = sinceIso.trim();
    const u = untilIso.trim();
    if (windowMode === "range" && s && u) {
      body.since_iso = s;
      body.until_iso = u;
    }
    return body;
  }, [
    advancedOpen,
    presetId,
    ticker,
    nBars,
    intervalAmount,
    intervalUnit,
    maxSteps,
    feeBps,
    initialCash,
    sinceIso,
    untilIso,
    windowMode,
    selected,
  ]);

  const fetchSeries = useCallback(async (runId: string) => {
    const base = getFlowApiOrigin();
    const [eqRes, trRes, barRes] = await Promise.all([
      fetch(`${base}/backtests/${encodeURIComponent(runId)}/equity?max_points=2500`),
      fetch(`${base}/backtests/${encodeURIComponent(runId)}/trades?limit=2000`),
      fetch(`${base}/backtests/${encodeURIComponent(runId)}/bars?max_points=2500`),
    ]);
    if (eqRes.ok) setEquitySeries((await eqRes.json()) as EquitySeriesResponse);
    else setEquitySeries(null);
    if (trRes.ok) setTradesData((await trRes.json()) as TradesResponse);
    else setTradesData(null);
    if (barRes.ok) setBarsData((await barRes.json()) as BarsResponse);
    else setBarsData(null);
  }, []);

  const fetchTracePayload = useCallback(async (runId: string, soft: boolean) => {
    const base = getFlowApiOrigin();
    const url = `${base}/runs/${encodeURIComponent(runId)}/payload${soft ? "?soft=true" : ""}`;
    try {
      const r = await fetch(url);
      if (r.ok) setTracePayload((await r.json()) as NexusPayload);
    } catch {
      // fetch failed (offline / CORS)
    }
  }, []);

  const loadHistoricalRun = useCallback(
    async (runId: string): Promise<boolean> => {
      if (!runId) return false;
      lastUrlRunRef.current = runId;
      router.replace(`/?view=${embedded ? embeddedView : "backtest"}&run=${encodeURIComponent(runId)}`, {
        scroll: false,
      });
      setHistoryLoading(true);
      setError(null);
      setRunPayload(null);
      setSummaryPayload(null);
      setEquitySeries(null);
      setTradesData(null);
      setTracePayload(null);
      setJobState(null);
      try {
        const base = getFlowApiOrigin();
        const sRes = await fetch(`${base}/backtests/${encodeURIComponent(runId)}/summary`);
        const raw = await sRes.json().catch(() => ({}));
        if (!sRes.ok) {
          setError(typeof raw.detail === "string" ? raw.detail : `HTTP ${sRes.status}`);
          return false;
        }
        setSummaryPayload(raw as SummaryPayload);
        setSelectedHistoryId(runId);
        await fetchSeries(runId);
        await fetchTracePayload(runId, false);
        return true;
      } catch (e) {
        setError(e instanceof Error ? e.message : "Request failed");
        return false;
      } finally {
        setHistoryLoading(false);
      }
    },
    [embedded, embeddedView, fetchSeries, fetchTracePayload, router],
  );

  const tryLoadHistoricalRunNoUrl = useCallback(
    async (runId: string): Promise<boolean> => {
      if (!runId) return false;
      setHistoryLoading(true);
      setError(null);
      setRunPayload(null);
      setSummaryPayload(null);
      setEquitySeries(null);
      setTradesData(null);
      setTracePayload(null);
      setJobState(null);
      try {
        const base = getFlowApiOrigin();
        const sRes = await fetch(`${base}/backtests/${encodeURIComponent(runId)}/summary`);
        const raw = await sRes.json().catch(() => ({}));
        if (!sRes.ok) {
          return false;
        }
        // Now that we know this run is actually persisted, update the URL + full series.
        lastUrlRunRef.current = runId;
        router.replace(`/?view=${embedded ? embeddedView : "backtest"}&run=${encodeURIComponent(runId)}`, {
          scroll: false,
        });
        setSummaryPayload(raw as SummaryPayload);
        setSelectedHistoryId(runId);
        await fetchSeries(runId);
        await fetchTracePayload(runId, false);
        return true;
      } catch {
        return false;
      } finally {
        setHistoryLoading(false);
      }
    },
    [embedded, embeddedView, fetchSeries, fetchTracePayload, router],
  );

  const jobRunning = !!pollingJobId && (jobState?.status === "running" || jobState?.status === "queued");

  useEffect(() => {
    if (!pollingJobId) return;
    const base = getFlowApiOrigin();
    let cancelled = false;

    const tick = async () => {
      try {
        const res = await fetch(`${base}/backtests/jobs/${encodeURIComponent(pollingJobId)}`);
        const j = (await res.json().catch(() => ({}))) as BacktestJob & { detail?: string };
        if (cancelled) return;
        if (!res.ok) {
          // Common when the server restarts: in-memory BACKTEST_JOBS is cleared.
          // In that case, only switch to a saved run if artifacts exist under `.runs/backtests/<id>/`.
          if (res.status === 404) {
            setPollingJobId(null);
            setLoading(false);
            if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
            const ok = await tryLoadHistoricalRunNoUrl(pollingJobId);
            if (!ok) {
              // Don't force &run= into the URL for an events-only / crashed run.
              setLiveRunId(null);
              setJobState(null);
              setError("Backtest job not found (server restarted). No saved artifacts were found for that run.");
            }
            return;
          }
          setError(typeof j.detail === "string" ? j.detail : `Job poll failed (HTTP ${res.status})`);
          return;
        }
        setJobState(j);
        if (j.status === "completed" && j.result) {
          setPollingJobId(null);
          setLiveRunId(null);
          setLoading(false);
          if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
          setRunPayload(j.result);
          if (j.result.run_id) {
            lastUrlRunRef.current = j.result.run_id;
            router.replace(`/?view=${embedded ? embeddedView : "backtest"}&run=${encodeURIComponent(j.result.run_id)}`, {
              scroll: false,
            });
            setSelectedHistoryId(j.result.run_id);
            await fetchSeries(j.result.run_id);
            await fetchTracePayload(j.result.run_id, false);
            fetch(`${base}/backtests`)
              .then((r) => r.json())
              .then((d: { runs?: string[] }) => {
                if (Array.isArray(d.runs)) setRunList(d.runs);
              })
              .catch(() => {});
          }
        }
        if (j.status === "failed") {
          setPollingJobId(null);
          setLiveRunId(null);
          setLoading(false);
          if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
          setError(typeof j.error === "string" ? j.error : "Backtest failed");
        }
      } catch {
        if (!cancelled) setError("Job poll failed");
      }
    };

    void tick();
    const id = window.setInterval(() => void tick(), 450);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [
    pollingJobId,
    embedded,
    embeddedView,
    fetchSeries,
    fetchTracePayload,
    loadHistoricalRun,
    tryLoadHistoricalRunNoUrl,
    router,
  ]);

  useEffect(() => {
    if (!liveRunId || !loading) return;
    const id = window.setInterval(() => {
      void fetchTracePayload(liveRunId, true);
    }, 850);
    return () => window.clearInterval(id);
  }, [liveRunId, loading, fetchTracePayload]);

  const runPreset = useCallback(async () => {
    setLoading(true);
    setError(null);
    setRunPayload(null);
    setSummaryPayload(null);
    setEquitySeries(null);
    setTradesData(null);
    setTracePayload(null);
    setJobState(null);
    setSelectedHistoryId("");
    setPollingJobId(null);
    setLiveRunId(null);

    const body = buildBody();
    const base = getFlowApiOrigin();

    try {
      const res = await fetch(`${base}/backtests/preset/async`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as { run_id?: string; detail?: string };
      if (!res.ok) {
        setLoading(false);
        setError(typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`);
        return;
      }
      if (!data.run_id) {
        setLoading(false);
        setError("No run_id from async endpoint");
        return;
      }
      setLiveRunId(data.run_id);
      setPollingJobId(data.run_id);
      setJobState({ status: "queued", step: 0, total_steps: 0 });
      if (typeof window !== "undefined") window.localStorage.setItem(LIVE_RUN_STORAGE_KEY, data.run_id);
    } catch (e) {
      setLoading(false);
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }, [buildBody]);

  const clearToNewRun = useCallback(() => {
    setHistoryLoading(false);
    setRunPayload(null);
    setSummaryPayload(null);
    setEquitySeries(null);
    setTradesData(null);
    setTracePayload(null);
    setSelectedHistoryId("");
    setError(null);
    lastUrlRunRef.current = null;
    router.replace(`/?view=${embedded ? embeddedView : "backtest"}`, { scroll: false });
  }, [embedded, embeddedView, router]);

  useEffect(() => {
    const id = initialRunId?.trim() || null;
    if (!id) {
      lastUrlRunRef.current = null;
      return;
    }
    if (id === lastUrlRunRef.current) return;
    void loadHistoricalRun(id);
  }, [initialRunId, loadHistoricalRun]);

  const metrics = runPayload?.metrics ?? summaryPayload?.metrics;
  const evaluation = runPayload?.evaluation;
  const activeRunId = runPayload?.run_id ?? summaryPayload?.run_id ?? "";

  const kpis = useMemo(() => {
    if (!metrics) return null;
    const eq0 = equitySeries?.points?.[0]?.equity;
    const eqN = equitySeries?.points?.[equitySeries.points.length - 1]?.equity;
    const initial = evaluation?.initial_cash ?? (metrics as { initial_cash?: number }).initial_cash ?? (typeof eq0 === "number" ? eq0 : NaN);
    const final = evaluation?.final_equity ?? (metrics as { final_equity?: number }).final_equity ?? (typeof eqN === "number" ? eqN : NaN);
    const retPct =
      evaluation?.total_return_pct ??
      (Number.isFinite(initial) && initial > 0 && Number.isFinite(final) ? ((final - initial) / initial) * 100 : 0);
    const trades = evaluation?.trade_count ?? runPayload?.trade_count ?? summaryPayload?.trade_count ?? 0;
    const steps = (metrics as { steps?: number }).steps ?? runPayload?.steps ?? summaryPayload?.steps ?? 0;
    const profitFactor = (metrics as { profit_factor?: number | null }).profit_factor ?? null;
    const rawWinRate = (metrics as { win_rate?: number }).win_rate;
    // If we don't have closed-trade PnLs, backend reports win_rate=0.0.
    // In that case, show "—" instead of a misleading 0.0%.
    const winRatePct =
      typeof rawWinRate === "number" && !(rawWinRate === 0 && profitFactor == null && trades > 0)
        ? rawWinRate * 100
        : null;
    return {
      totalReturnPct: retPct,
      sharpe: metrics.sharpe,
      maxDrawdownPct: metrics.max_drawdown * 100,
      winRatePct,
      profitFactor,
      trades,
      steps,
      finalEquity: final,
      initialCash: initial,
      intervalSec: metrics.interval_sec,
    };
  }, [metrics, evaluation, runPayload, summaryPayload, equitySeries]);

  useEffect(() => {
    if (!embedded) return;
    if (activeRunId) setEmbeddedTab("saved");
  }, [embedded, activeRunId]);

  const displayPayload = runPayload ?? (summaryPayload as unknown as BacktestRunResult | null);

  const tracesToShow = tracePayload?.traces ?? [];
  const messageLog = tracePayload?.message_log ?? [];
  const streamingThoughts = jobRunning && embeddedTab === "new";
  const timelineEmptyHint =
    embedded &&
    kpis &&
    !streamingThoughts &&
    messageLog.length === 0 &&
    tracesToShow.length === 0
      ? "This run loaded, but the saved trace has no bar events yet. Re-run the backtest or check GET /runs/<id>/payload (message_log)."
      : null;
  const formBusy = jobRunning || loading || historyLoading;

  const progressPct =
    jobState?.total_steps && jobState.total_steps > 0 && jobState.step != null
      ? Math.min(100, Math.round((jobState.step / jobState.total_steps) * 100))
      : 0;

  function renderSetupForm(compactForm = false) {
    const lb = compactForm ? "block font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]" : "block font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]";
    const inp = compactForm
      ? "mt-1 w-full rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px]"
      : "mt-2 w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 py-2.5 font-mono text-xs";
    const sel = compactForm
      ? "mt-1 w-full rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px] text-[var(--nexus-text)]"
      : "mt-2 w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 py-2.5 font-mono text-xs text-[var(--nexus-text)]";
    return (
      <>
        <div className={`flex flex-wrap items-end ${compactForm ? "gap-3" : "gap-6"}`}>
          <div className={`min-w-0 flex-1 ${compactForm ? "min-w-[140px]" : "min-w-[200px]"}`}>
            <label className={lb}>Strategy preset</label>
            <select
              className={sel}
              value={presetId}
              onChange={(e) => setPresetId(e.target.value)}
              disabled={formBusy}
            >
              {strategies.length === 0 ? (
                <option value="macd_risk_v1">macd_risk_v1</option>
              ) : (
                strategies.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))
              )}
            </select>
            {selected ? (
              <p
                className={`mt-1.5 text-[var(--nexus-muted)] ${compactForm ? "line-clamp-2 text-[10px] leading-snug" : "mt-2 text-[11px] leading-relaxed"}`}
              >
                {selected.description}
              </p>
            ) : null}
          </div>
          <div className={`w-full min-w-[120px] ${compactForm ? "max-w-[11rem]" : "max-w-xs min-w-[160px]"}`}>
            <label className={lb}>Ticker</label>
            <input
              className={inp}
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
              placeholder="BTC/USDT"
              disabled={formBusy}
            />
          </div>
        </div>

        <div className={compactForm ? "mt-3" : "mt-5"}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className={`font-mono uppercase tracking-[0.2em] text-[var(--nexus-muted)] ${compactForm ? "text-[9px]" : "text-[10px]"}`}>
              Backtest
            </p>
          </div>
          <div
            className={`mt-2 grid grid-cols-1 sm:grid-cols-2 ${compactForm ? "gap-2" : "mt-3 gap-4 sm:items-start"}`}
          >
            <div className="min-w-0">
              <label className={lb}>Candles</label>
              <input
                className={`${inp} tabular-nums`}
                inputMode="numeric"
                value={nBars}
                onChange={(e) => setNBars(e.target.value)}
                disabled={formBusy}
                aria-label="Number of candles"
              />
              {!compactForm ? (
                <p className="mt-0.5 text-[10px] text-[var(--nexus-muted)]">How many OHLCV candles to fetch</p>
              ) : null}
            </div>
            <div
              className={`min-w-0 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/60 ${compactForm ? "p-2" : "p-3"}`}
            >
              <label className={lb}>Data window</label>
              <div className="mt-1 flex flex-wrap items-center gap-2">
                <div className="flex flex-wrap gap-2" role="group" aria-label="Data window mode">
                  <button
                    type="button"
                    onClick={() => setWindowMode("range")}
                    disabled={formBusy}
                    className={`rounded-lg px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest ring-1 transition focus:outline-none focus:ring-1 focus:ring-cyan-500/40 ${
                      windowMode === "range"
                        ? "bg-[rgba(34,211,238,0.14)] text-[#22d3ee] ring-[rgba(34,211,238,0.35)]"
                        : "bg-white/[0.03] text-[var(--nexus-muted)] ring-white/10 hover:bg-white/[0.05] hover:text-[var(--nexus-text)]"
                    }`}
                  >
                    Date range (UTC)
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setWindowMode("latest");
                      setSinceIso("");
                      setUntilIso("");
                    }}
                    disabled={formBusy}
                    className={`rounded-lg px-3 py-1.5 font-mono text-[10px] uppercase tracking-widest ring-1 transition focus:outline-none focus:ring-1 focus:ring-cyan-500/40 ${
                      windowMode === "latest"
                        ? "bg-[rgba(34,211,238,0.10)] text-[#22d3ee] ring-[rgba(34,211,238,0.28)]"
                        : "bg-white/[0.03] text-[var(--nexus-muted)] ring-white/10 hover:bg-white/[0.05] hover:text-[var(--nexus-text)]"
                    }`}
                  >
                    Latest N candles
                  </button>
                </div>
                <span className="hidden h-3 w-px shrink-0 bg-white/10 sm:block" aria-hidden />
                {windowMode === "range" ? (
                  <span
                    className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]"
                    title="Start and end dates are fixed for this run"
                  >
                    Pinned range
                  </span>
                ) : (
                  <span
                    className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]"
                    title="Uses the latest N candles from the exchange"
                  >
                    Rolling window
                  </span>
                )}
              </div>
              {windowMode === "range" ? (
                <div className="mt-2 space-y-2">
                  <div className="flex w-full max-w-full flex-col gap-2 sm:max-w-none sm:flex-row sm:flex-wrap sm:items-end sm:gap-x-3 sm:gap-y-2">
                    <div className="min-w-0 sm:w-[min(100%,12rem)]">
                      <label className={lb}>Start (UTC)</label>
                      <DatePickerField
                        label="Start (UTC)"
                        value={sinceIso}
                        onChange={(next) => {
                          setSinceIso(next);
                          if (untilIso && next && untilIso < next) setUntilIso(next);
                        }}
                        disabled={formBusy}
                        className={inp}
                        placeholder="YYYY-MM-DD"
                      />
                    </div>
                    <span
                      className="select-none py-0.5 text-center font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] sm:shrink-0 sm:self-end sm:pb-2.5"
                      aria-hidden
                    >
                      to
                    </span>
                    <div className="min-w-0 sm:w-[min(100%,12rem)]">
                      <label className={lb}>End (UTC)</label>
                      <DatePickerField
                        label="End (UTC)"
                        value={untilIso}
                        onChange={setUntilIso}
                        minIso={sinceIso || undefined}
                        disabled={formBusy}
                        className={inp}
                        placeholder="YYYY-MM-DD"
                      />
                    </div>
                  </div>
                  {!compactForm ? (
                    <p className="text-[10px] text-[var(--nexus-muted)]">
                      Inclusive UTC dates; the bar interval below defines candle spacing inside this span.
                    </p>
                  ) : null}
                </div>
              ) : (
                <div className="mt-2 rounded-lg border border-dashed border-white/10 bg-white/[0.02] px-3 py-2.5">
                  <p className="text-[12px] leading-snug text-[var(--nexus-text)]">
                    No start/end dates — use <span className="font-mono text-[var(--nexus-muted)]">Candles</span> (left) and
                    your bar interval. Fetches the latest N candles from the exchange.
                  </p>
                </div>
              )}
            </div>
            <div>
              <label className={lb}>Time between bars</label>
              <div className="mt-1 flex flex-wrap gap-1.5">
                <input
                  type="text"
                  inputMode="decimal"
                  className={
                    compactForm
                      ? "min-w-[3rem] flex-1 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px]"
                      : "min-w-[4rem] flex-1 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-2 font-mono text-xs"
                  }
                  value={intervalAmount}
                  onChange={(e) => setIntervalAmount(e.target.value)}
                  disabled={formBusy}
                  aria-label="Bar interval amount"
                />
                <select
                  className={
                    compactForm
                      ? "min-w-[6rem] flex-1 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px] text-[var(--nexus-text)]"
                      : "min-w-[8rem] flex-1 rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-2 font-mono text-xs text-[var(--nexus-text)]"
                  }
                  value={intervalUnit}
                  onChange={(e) => setIntervalUnit(e.target.value as BarIntervalUnit)}
                  disabled={formBusy}
                  aria-label="Bar interval unit"
                >
                  {(Object.keys(BAR_INTERVAL_UNIT_LABEL) as BarIntervalUnit[]).map((u) => (
                    <option key={u} value={u}>
                      {BAR_INTERVAL_UNIT_LABEL[u]}
                    </option>
                  ))}
                </select>
              </div>
              {!compactForm ? (
                <p className="mt-0.5 text-[10px] text-[var(--nexus-muted)]">Bar spacing (sent to the API as seconds).</p>
              ) : null}
            </div>
            <div className="min-w-0">
              <label className={lb}>Max graph steps</label>
              <input
                className={`${inp} tabular-nums`}
                inputMode="numeric"
                value={maxSteps}
                onChange={(e) => setMaxSteps(e.target.value)}
                disabled={formBusy}
                aria-label="Max graph steps"
              />
              {!compactForm ? (
                <p className="mt-0.5 text-[10px] text-[var(--nexus-muted)]">Safety cap on LangGraph steps per bar</p>
              ) : null}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setAdvancedOpen((o) => !o)}
          className={`font-mono uppercase tracking-widest text-[var(--nexus-glow)] hover:underline ${compactForm ? "mt-2 text-[9px]" : "mt-4 text-[10px]"}`}
        >
          {advancedOpen ? "Hide advanced (fees, capital)" : "Advanced: fees, initial capital"}
        </button>

        {advancedOpen ? (
          <div className={`grid sm:grid-cols-2 lg:grid-cols-3 ${compactForm ? "mt-2 gap-2" : "mt-4 gap-4"}`}>
            {(
              [
                ["fee_bps", feeBps, setFeeBps, "Trading fee in basis points"],
                ["initial_cash", initialCash, setInitialCash, "Starting quote balance"],
              ] as const
            ).map(([key, val, setVal, hint]) => (
              <div key={key}>
                <label className={lb}>{key === "fee_bps" ? "Fee (bps)" : "Initial cash"}</label>
                <input
                  className={inp}
                  value={val}
                  onChange={(e) => setVal(e.target.value)}
                  disabled={formBusy}
                />
                {!compactForm ? <p className="mt-0.5 text-[10px] text-[var(--nexus-muted)]">{hint}</p> : null}
              </div>
            ))}
          </div>
        ) : null}

        <div className={`flex flex-col ${compactForm ? "mt-3 gap-2" : "mt-6 gap-4"}`}>
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              disabled={formBusy}
              onClick={() => void runPreset()}
              className={
                compactForm
                  ? "rounded-md border border-[color:var(--nexus-glow)]/50 bg-[var(--nexus-glow)]/15 px-4 py-2 font-mono text-[10px] font-medium uppercase tracking-wider text-[var(--nexus-glow)] transition hover:bg-[var(--nexus-glow)]/25 disabled:opacity-50"
                  : "rounded-lg border border-[color:var(--nexus-glow)]/50 bg-[var(--nexus-glow)]/15 px-5 py-2.5 font-mono text-[11px] font-medium uppercase tracking-widest text-[var(--nexus-glow)] shadow-[0_0_20px_rgba(0,212,170,0.12)] transition hover:bg-[var(--nexus-glow)]/25 disabled:opacity-50"
              }
            >
              {streamingThoughts ? "Running replay…" : "Run backtest"}
            </button>
            {(summaryPayload || runPayload) && !streamingThoughts ? (
              <button
                type="button"
                onClick={() => {
                  clearToNewRun();
                  if (embedded) setEmbeddedTab("new");
                }}
                className={
                  compactForm
                    ? "rounded-md border border-[color:var(--nexus-card-stroke)] px-3 py-2 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] transition hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
                    : "rounded-lg border border-[color:var(--nexus-card-stroke)] px-4 py-2.5 font-mono text-[11px] uppercase tracking-widest text-[var(--nexus-muted)] transition hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
                }
              >
                Configure new run
              </button>
            ) : null}
          </div>
          {/* Standalone run picker lives in the page header area (not inside the setup form). */}
        </div>

        {jobRunning && jobState ? (
        <div
            className={`space-y-1.5 rounded-lg border border-[color:var(--nexus-glow)]/25 bg-[var(--nexus-glow)]/5 ${compactForm ? "mt-2 p-2" : "mt-4 space-y-2 p-3"}`}
          >
            <div className="flex justify-between font-mono text-[10px] text-[var(--nexus-muted)]">
              <span>Bar replay progress</span>
              <span>
                {jobState.step ?? 0} / {jobState.total_steps || "…"} bars ({progressPct}%)
              </span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--nexus-surface)]">
              <div
                className="h-full bg-[var(--nexus-glow)] transition-[width] duration-300"
                style={{ width: `${progressPct}%` }}
              />
            </div>
            <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
              Equity{" "}
              {typeof jobState.equity === "number"
                ? jobState.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })
                : "…"}{" "}
              · fills {jobState.trade_count ?? 0}
              {jobState.vetoed != null ? ` · last bar veto: ${jobState.vetoed ? "yes" : "no"}` : ""}
            </p>
          </div>
        ) : null}

        {!embedded ? (
          <p className="mt-4 text-[10px] leading-relaxed text-[var(--nexus-muted)]">
            Async job + browser polling. Set <code className="text-[var(--nexus-text)]">NEXT_PUBLIC_FLOW_API_BASE_URL</code>{" "}
            if the API is not on <code className="text-[var(--nexus-text)]">127.0.0.1:8001</code>.
          </p>
        ) : null}
      </>
    );
  }

  function renderResultsDetail(variant: "embedded" | "standalone") {
    if (!kpis) return null;
    const compact = variant === "embedded";
    const card = compact
      ? "rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-2.5"
      : "rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4";
    const h3 = compact
      ? "font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]"
      : "font-mono text-[11px] uppercase tracking-widest text-[var(--nexus-muted)]";
    return (
      <section
        id="backtest-results-detail"
        className={compact ? "scroll-mt-2 space-y-2 pb-1" : "scroll-mt-3 space-y-4 pb-2"}
      >
        {variant === "standalone" ? (
          <>
            <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Results</h2>
            <BacktestKpiGrid kpis={kpis} />
          </>
        ) : (
          <>
            <h2 className="font-mono text-[9px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">Performance</h2>
            <BacktestKpiGrid kpis={kpis} compact />
          </>
        )}

        <div className={card}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className={h3}>Price + equity</h3>
            {equitySeries?.downsampled ? (
              <span className="font-mono text-[9px] text-[var(--nexus-muted)]">
                Chart: {equitySeries.points.length} pts (of {equitySeries.count})
              </span>
            ) : equitySeries ? (
              <span className="font-mono text-[9px] text-[var(--nexus-muted)]">{equitySeries.count} bars</span>
            ) : null}
          </div>
          {!compact ? (
            <p className="mb-3 text-[10px] text-[var(--nexus-muted)]">
              Candles show price action; arrows show fills. Equity is the strategy curve below.
            </p>
          ) : (
            <p className="mb-1.5 text-[9px] text-[var(--nexus-muted)]">Candles = price · arrows = fills</p>
          )}
          <div className="mb-3 min-w-0">
            <BacktestPriceChart
              bars={(barsData?.bars ?? []) as OhlcvBar[]}
              trades={(tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? [])}
              height={compact ? 240 : 300}
            />
          </div>
          <BacktestEquityChart
            points={equitySeries?.points ?? []}
            initialCash={kpis.initialCash}
            trades={(tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? [])}
          />
        </div>

        <div className={compact ? "grid gap-2 lg:grid-cols-2" : "grid gap-4 lg:grid-cols-2"}>
          <div className={card}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className={h3}>Trade fills</h3>
              <span className="font-mono text-[9px] text-[var(--nexus-muted)]">
                {kpis.trades.toLocaleString()} fills
              </span>
            </div>
            <div className={compact ? "mt-1.5" : "mt-3"}>
              <BacktestTradesTable
                trades={(tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? [])}
                truncated={tradesData?.truncated}
                total={tradesData?.total}
                returned={tradesData?.returned}
              />
            </div>
            {kpis.trades === 0 ? (
              <p className={`text-[var(--nexus-muted)] ${compact ? "mt-2 text-[9px] leading-snug" : "mt-3 text-[10px] leading-relaxed"}`}>
                {compact
                  ? "No fills — see timeline for desk / risk detail."
                  : "No simulated fills: the combined desk signals and synthesis path likely did not yield a buy that cleared portfolio and risk rules, or position sizing was zero. Use the bar timeline to inspect each desk, the evidence board, arbitrator output, and risk guard per step."}
              </p>
            ) : null}
          </div>
          <div className={card}>
            <h3 className={h3}>Run details</h3>
            <dl className={`space-y-1.5 font-mono ${compact ? "mt-1.5 text-[10px]" : "mt-3 space-y-2 text-[11px]"}`}>
              <div className="flex justify-between gap-4 border-b border-[color:var(--nexus-rule-soft)] pb-2">
                <dt className="text-[var(--nexus-muted)]">Run ID</dt>
                <dd className="max-w-[60%] break-all text-right text-[var(--nexus-glow)]">{activeRunId || "—"}</dd>
              </div>
              <div className="flex justify-between gap-4 border-b border-[color:var(--nexus-rule-soft)] pb-2">
                <dt className="text-[var(--nexus-muted)]">Final equity</dt>
                <dd className="tabular-nums">
                  {typeof kpis.finalEquity === "number"
                    ? kpis.finalEquity.toLocaleString(undefined, { maximumFractionDigits: 2 })
                    : "—"}
                </dd>
              </div>
              <div className="flex justify-between gap-4 border-b border-[color:var(--nexus-rule-soft)] pb-2">
                <dt className="text-[var(--nexus-muted)]">Bar interval</dt>
                <dd className="text-right">
                  {formatIntervalHuman(kpis.intervalSec)}{" "}
                  <span className="text-[var(--nexus-muted)]">({kpis.intervalSec}s)</span>
                </dd>
              </div>
              {runPayload?.strategy?.title ? (
                <div className="flex justify-between gap-4 border-b border-[color:var(--nexus-rule-soft)] pb-2">
                  <dt className="text-[var(--nexus-muted)]">Strategy</dt>
                  <dd className="text-right">{runPayload.strategy.title}</dd>
                </div>
              ) : null}
              {runPayload?.capped ? (
                <div className="rounded border border-amber-900/40 bg-amber-950/25 px-2 py-2 text-[10px] text-amber-100">
                  Run capped by server max steps ({runPayload.server_max_steps ?? "—"}).
                </div>
              ) : null}
              {evaluation?.note ? (
                <div className="text-[10px] leading-relaxed text-[var(--nexus-muted)]">{evaluation.note}</div>
              ) : null}
            </dl>
            <div className={`flex flex-wrap items-center justify-end gap-1.5 ${compact ? "mt-2" : "mt-4 gap-2"}`}>
              <button
                type="button"
                disabled={!activeRunId}
                onClick={() => {
                  if (!activeRunId) return;
                    // In Research mode, keep the user in the split workspace.
                    const nextView = embedded && embeddedView === "research" ? "research" : "supervisor";
                    router.replace(`/?view=${nextView}&run=${encodeURIComponent(activeRunId)}`, { scroll: false });
                }}
                className={`rounded border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] font-mono uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40 ${
                  compact ? "px-2 py-1 text-[9px]" : "px-3 py-1.5 text-[10px]"
                }`}
              >
                Ask Supervisor
              </button>
              <details className="relative">
                <summary
                  className={`list-none cursor-pointer rounded border border-[color:var(--nexus-card-stroke)] font-mono uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/40 hover:text-[var(--nexus-text)] ${
                    compact ? "px-2 py-1 text-[9px]" : "px-3 py-1.5 text-[10px]"
                  }`}
                >
                  More
                </summary>
                <div className="absolute right-0 mt-2 w-44 overflow-hidden rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/95 shadow-[0_10px_30px_rgba(0,0,0,0.35)] backdrop-blur">
                  <button
                    type="button"
                    disabled={!activeRunId}
                    onClick={() => {
                      if (!activeRunId) return;
                      void copyText(activeRunId);
                    }}
                    className="block w-full px-3 py-2 text-left font-mono text-[11px] text-[var(--nexus-text)] hover:bg-[var(--nexus-surface)] disabled:opacity-40"
                  >
                    Copy run id
                  </button>
                  <button
                    type="button"
                    disabled={!displayPayload}
                    onClick={() =>
                      displayPayload && downloadJson(displayPayload, `${activeRunId || "backtest"}-result.json`)
                    }
                    className="block w-full px-3 py-2 text-left font-mono text-[11px] text-[var(--nexus-text)] hover:bg-[var(--nexus-surface)] disabled:opacity-40"
                  >
                    Download JSON
                  </button>
                </div>
              </details>
            </div>
          </div>
        </div>

        <div className={compact ? "h-0.5" : "h-2"} />
      </section>
    );
  }

  const rootClass = embedded
    ? "flex min-h-0 flex-1 flex-col overflow-hidden bg-[var(--nexus-bg)] text-[var(--nexus-text)]"
    : "nexus-bg min-h-screen bg-[var(--nexus-bg)] text-[var(--nexus-text)]";

  return (
    <div className={rootClass}>
      {embedded ? (
        <div className="flex min-h-0 w-full flex-1 flex-col overflow-hidden">
          <EmbeddedBacktestChrome
            tab={embeddedTab}
            onTabChange={(t) => {
              setEmbeddedTab(t);
              if (t === "new") clearToNewRun();
            }}
            runList={runList}
            selectedHistoryId={selectedHistoryId}
            historyLoading={historyLoading}
            activeRunId={activeRunId}
            shortRunLabel={shortBacktestRunLabel}
            onSelectRun={(id) => void loadHistoricalRun(id)}
            onClearRun={clearToNewRun}
          />

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {error ? (
              <div
                className="shrink-0 border-b border-red-900/45 bg-red-950/35 px-3 py-1.5 font-mono text-[10px] text-red-100"
                role="alert"
              >
                {error}
              </div>
            ) : null}
            <div className="flex min-h-0 min-w-0 flex-1 flex-col">
              <div className="nexus-scroll flex min-h-0 flex-1 flex-col gap-3 overflow-x-hidden overflow-y-auto px-3 pb-4 pt-3">
                {jobRunning && embeddedTab === "saved" ? (
                  <div className="shrink-0 rounded-lg border border-[color:var(--nexus-glow)]/25 bg-[var(--nexus-glow)]/5 px-2 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                        Live backtest running
                      </p>
                      <button
                        type="button"
                        onClick={() => setEmbeddedTab("new")}
                        className="rounded border border-[color:var(--nexus-glow)]/45 bg-[var(--nexus-glow)]/10 px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[var(--nexus-glow)]/15"
                      >
                        Resume
                      </button>
                    </div>
                    <p className="mt-1 font-mono text-[9px] text-[var(--nexus-muted)]">
                      {jobState?.step ?? 0}/{jobState?.total_steps || "…"} bars · fills {jobState?.trade_count ?? 0}
                    </p>
                  </div>
                ) : null}
                {embeddedTab === "saved" ? (
                  <div className="flex w-full max-w-none min-h-0 flex-1 flex-col gap-3">
                    {!historyLoading && kpis ? (
                      <section className="flex min-h-0 flex-1 flex-col gap-3">
                        <div className="min-w-0 shrink-0">{renderResultsDetail("embedded")}</div>
                        <section id="backtest-timeline" className="flex min-h-0 flex-1 flex-col">
                          <h2 className="shrink-0 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                            Timeline
                          </h2>
                          <p className="mt-0.5 font-mono text-[8px] text-[var(--nexus-muted)]">
                            Expand a bar: chain-of-thought and event log sit in two columns when the panel is wide enough.
                          </p>
                          <div className="mt-1.5 flex min-h-[min(44vh,520px)] flex-1 flex-col overflow-hidden rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/30">
                            <div className="min-h-0 flex-1 overflow-hidden p-1">
                              <BacktestBarTimeline
                                entries={messageLog}
                                traces={tracesToShow}
                                streaming={streamingThoughts}
                                emptyHint={timelineEmptyHint}
                                compact
                                className="h-full min-h-0 w-full text-[10px]"
                              />
                            </div>
                          </div>
                        </section>
                      </section>
                    ) : null}
                  </div>
                ) : null}

                {embeddedTab === "new" ? (
                  <section
                    id="backtest-setup"
                    className="scroll-mt-1 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/75 p-3"
                  >
                    {renderSetupForm(true)}

                    {streamingThoughts || tracesToShow.length > 0 || messageLog.length > 0 ? (
                      <section className="mt-3 border-t border-[color:var(--nexus-rule-soft)] pt-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h2 className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                              Live timeline
                            </h2>
                            <p className="mt-0.5 font-mono text-[8px] text-[var(--nexus-muted)]">
                              Updates while the replay runs (soft payload). Expand a bar for CoT + log.
                            </p>
                          </div>
                        </div>
                        <div className="mt-1.5 flex min-h-[min(42vh,420px)] flex-1 flex-col overflow-hidden rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/30">
                          <div className="min-h-0 flex-1 overflow-hidden p-1">
                            <BacktestBarTimeline
                              entries={messageLog}
                              traces={tracesToShow}
                              streaming={streamingThoughts}
                              emptyHint={timelineEmptyHint}
                              compact
                              className="h-full min-h-0 w-full text-[10px]"
                            />
                          </div>
                        </div>
                      </section>
                    ) : null}
                  </section>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {!embedded ? (
        <header className="border-b border-[color:var(--nexus-rule-strong)] bg-[var(--nexus-panel)]/95 px-4 py-4">
          <div className="mx-auto flex max-w-6xl flex-wrap items-start justify-between gap-4">
            <div>
              <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-[var(--nexus-glow)]">
                Multi-agent workflow
              </p>
              <h1 className="text-lg font-semibold tracking-tight">Backtest lab</h1>
              <p className="mt-2 max-w-2xl text-[12px] leading-relaxed text-[var(--nexus-muted)]">
                Replays the full LangGraph once per OHLCV bar. Traces use the same FlowEvent contract
                as live runs: perception desks, evidence board + arbitration, risk guard, and execution — with
                structured reasoning visible in the timeline.
              </p>
            </div>
          </div>
        </header>
      ) : null}

      <div
        className={
          embedded
            ? "hidden"
            : "mx-auto max-w-6xl space-y-6 px-4 py-8"
        }
      >
        {!embedded ? (
          <>
            <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                    Run picker
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-[var(--nexus-muted)]">
                    {activeRunId ? (
                      <>
                        Active: <span className="text-[var(--nexus-glow)]">{activeRunId}</span>
                      </>
                    ) : (
                      "No run loaded yet."
                    )}
                  </p>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  {runList.length > 0 ? (
                    <select
                      className="h-9 w-full max-w-[28rem] rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 font-mono text-[11px] text-[var(--nexus-text)] sm:w-[28rem]"
                      value={selectedHistoryId}
                      disabled={historyLoading}
                      title={selectedHistoryId || "Choose a completed run"}
                      onChange={(e) => {
                        const id = e.target.value.trim();
                        if (id) void loadHistoricalRun(id);
                        else clearToNewRun();
                      }}
                    >
                      <option value="">Saved runs…</option>
                      {[...runList].reverse().map((id) => (
                        <option key={id} value={id} title={id}>
                          {shortBacktestRunLabel(id)}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="font-mono text-[11px] text-[var(--nexus-muted)]">No saved runs</span>
                  )}
                  <button
                    type="button"
                    disabled={historyLoading || runList.length === 0}
                    onClick={() => {
                      const latest = [...runList].slice(-1)[0];
                      if (latest) void loadHistoricalRun(latest);
                    }}
                    className="h-9 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)] disabled:opacity-40"
                  >
                    Latest
                  </button>
                  <button
                    type="button"
                    disabled={!activeRunId}
                    onClick={() => {
                      if (!activeRunId) return;
                      const nextView = embedded && embeddedView === "research" ? "research" : "supervisor";
                      router.replace(`/?view=${nextView}&run=${encodeURIComponent(activeRunId)}`, { scroll: false });
                    }}
                    className="h-9 rounded-lg border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
                  >
                    Ask Supervisor
                  </button>
                </div>
              </div>
            </section>

            <section
              id="backtest-setup"
              className="scroll-mt-4 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/80 p-5 shadow-[0_0_24px_rgba(0,212,170,0.06)]"
            >
              {renderSetupForm()}
            </section>

            {error ? (
              <div className="rounded-lg border border-red-900/50 bg-red-950/35 px-4 py-3 font-mono text-xs text-red-100">
                {error}
              </div>
            ) : null}

            {(kpis || streamingThoughts || tracesToShow.length > 0 || messageLog.length > 0) ? (
              <section className="grid w-full grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
                <div className="min-w-0 space-y-4">
                  <div className="min-w-0">{kpis ? renderResultsDetail("standalone") : null}</div>

                  <section className="flex min-h-[320px] w-full flex-col overflow-hidden rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
                    <div className="shrink-0 space-y-2 border-b border-[color:var(--nexus-rule-soft)] px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                          Bar timeline
                        </h3>
                        <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--nexus-muted)]">
                          Expand a bar: chain-of-thought and event log use two columns when the panel is wide enough.
                        </p>
                      </div>
                    </div>
                    <div className="flex min-h-[240px] flex-1 flex-col gap-2 p-2">
                      <BacktestBarTimeline
                        entries={messageLog}
                        traces={tracesToShow}
                        streaming={streamingThoughts}
                        emptyHint={timelineEmptyHint}
                        className="min-h-0 flex-1 p-0.5"
                      />
                    </div>
                  </section>
                </div>

                <aside className="flex min-h-0 flex-col gap-4">
                  <section className="rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
                          Insight
                        </p>
                        <p className="mt-2 text-[12px] leading-relaxed text-[var(--nexus-text)]">
                          {kpis ? (
                            <>
                              Final equity{" "}
                              <span className="font-mono">
                                {typeof kpis.finalEquity === "number"
                                  ? kpis.finalEquity.toLocaleString(undefined, { maximumFractionDigits: 2 })
                                  : "—"}
                              </span>
                              .{" "}
                              {typeof kpis.maxDrawdownPct === "number" ? (
                                <>
                                  Max DD{" "}
                                  <span className="font-mono">
                                    {(kpis.maxDrawdownPct * 100).toFixed(2)}%
                                  </span>
                                  .
                                </>
                              ) : null}
                            </>
                          ) : (
                            <span className="text-[var(--nexus-muted)]">Run data will appear here.</span>
                          )}
                        </p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        disabled={!activeRunId}
                        onClick={() => {
                          if (!activeRunId) return;
                          const nextView = embedded && embeddedView === "research" ? "research" : "supervisor";
                          router.replace(`/?view=${nextView}&run=${encodeURIComponent(activeRunId)}`, { scroll: false });
                        }}
                        className="h-9 rounded-lg border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
                      >
                        Ask Supervisor
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          const el = document.getElementById("backtest-setup");
                          el?.scrollIntoView({ block: "start" });
                        }}
                        className="h-9 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)]"
                      >
                        Edit config
                      </button>
                    </div>
                  </section>
                </aside>
              </section>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
