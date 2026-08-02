"use client";

import {
  memo,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { BacktestBarTimeline } from "@/components/backtest/BacktestBarTimeline";
import {
  EmbeddedBacktestChrome,
  type EmbeddedWorkspaceTab,
  type SavedRunListItem,
} from "@/components/backtest/EmbeddedBacktestChrome";
import { BacktestEquityChart } from "@/components/backtest/BacktestEquityChart";
import { BacktestDrawdownChart } from "@/features/backtest/components/BacktestDrawdownChart";
import { BacktestTradesTable } from "@/components/backtest/BacktestTradesTable";
import { copyText } from "@/components/backtest/embeddedBacktestUtils";
import {
  StrategyCardSelector,
  ReasoningPreviewCard,
  type StrategyOption,
} from "@/components/StrategyCardSelector";
import { FutuTickerCombobox } from "@/components/FutuTickerCombobox";
import { BacktestPriceChart } from "@/features/backtest/components/BacktestPriceChart";
import { BacktestReportInsights } from "@/features/backtest/components/BacktestReportInsights";
import { format, parseISO } from "date-fns";
import { createPortal } from "react-dom";
import ReactDatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {
  amountUnitToIntervalSec,
  formatIntervalHuman,
  intervalSecToAmountUnit,
  type BarIntervalUnit,
} from "@/lib/backtestInterval";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { researchConsoleHref } from "@/lib/consoleView";
import { useDeskOwnership } from "@/hooks/useDeskOwnership";
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

type StrategyRow = StrategyOption;

type BacktestJob = {
  status: "queued" | "running" | "completed" | "failed";
  step?: number;
  total_steps?: number;
  trade_count?: number;
  equity?: number;
  capital?: number;
  positions?: number;
  vetoed?: boolean;
  warmup?: boolean;
  error?: string;
  result?: BacktestRunResult;
};

function formatJobBookLine(job: BacktestJob): string {
  const parts: string[] = [];
  if (typeof job.equity === "number" && Number.isFinite(job.equity)) {
    parts.push(
      `Equity $${job.equity.toLocaleString(undefined, { maximumFractionDigits: 2 })}`,
    );
  } else {
    parts.push("Equity …");
  }
  const open = typeof job.positions === "number" ? job.positions : 0;
  const closed = typeof job.trade_count === "number" ? job.trade_count : 0;
  if (open > 0) parts.push(`${open} open`);
  parts.push(`${closed} closed`);
  return parts.join(" · ");
}

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

function defaultDateRange(daysBack: number): { since: string; until: string } {
  const until = new Date();
  const since = new Date();
  since.setUTCDate(since.getUTCDate() - Math.max(1, daysBack));
  return { since: dateToIso(since), until: dateToIso(until) };
}

const CRYPTO_SYMBOLS = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT"] as const;
const STOCK_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "SPY", "QQQ"] as const;

const DEFAULT_TF_AMOUNT = "1";
const DEFAULT_TF_UNIT: BarIntervalUnit = "day";
const DEFAULT_LOOKBACK_DAYS = 60;

const TIMEFRAME_PRESETS: { id: string; label: string; amount: string; unit: BarIntervalUnit }[] = [
  { id: "1m", label: "1m", amount: "1", unit: "min" },
  { id: "5m", label: "5m", amount: "5", unit: "min" },
  { id: "15m", label: "15m", amount: "15", unit: "min" },
  { id: "1h", label: "1h", amount: "1", unit: "hr" },
  { id: "4h", label: "4h", amount: "4", unit: "hr" },
  { id: "1d", label: "1d", amount: "1", unit: "day" },
];

function matchTimeframePreset(amount: string, unit: BarIntervalUnit): string | null {
  const hit = TIMEFRAME_PRESETS.find((p) => p.amount === amount && p.unit === unit);
  return hit?.id ?? null;
}

// Portal host must be stable — inline `() => document.body` remounts the calendar every render.
function DatePickerPopperContainer({ children }: { children?: ReactNode }) {
  if (typeof document === "undefined") return null;
  return createPortal(children, document.body);
}

const DatePickerField = memo(function DatePickerField({
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
  placeholder?: string;
}) {
  const selected = useMemo(() => isoToDate(value), [value]);
  const minDate = useMemo(() => (minIso ? isoToDate(minIso) : null), [minIso]);
  const onChangeStable = useCallback(
    (d: Date | null) => {
      if (!d) {
        onChange("");
        return;
      }
      onChange(dateToIso(d));
    },
    [onChange],
  );

  return (
    <div className="relative">
      <label className="sr-only">{label}</label>
      <ReactDatePicker
        selected={selected}
        onChange={onChangeStable}
        minDate={minDate ?? undefined}
        disabled={disabled}
        dateFormat="yyyy-MM-dd"
        showMonthDropdown
        showYearDropdown
        dropdownMode="select"
        placeholderText={placeholder ?? label}
        popperPlacement="bottom-start"
        popperContainer={DatePickerPopperContainer}
        popperClassName="nexus-datepicker-popper"
        calendarClassName="nexus-datepicker"
        className={`${className} text-left`}
        shouldCloseOnSelect
      />
    </div>
  );
});

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

function formatFlowError(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail.map((item) => {
      if (item && typeof item === "object" && "msg" in item) {
        const loc = Array.isArray((item as { loc?: unknown }).loc)
          ? (item as { loc: unknown[] }).loc.join(".")
          : "";
        const msg = String((item as { msg: unknown }).msg);
        return loc ? `${loc}: ${msg}` : msg;
      }
      return typeof item === "string" ? item : JSON.stringify(item);
    });
    const joined = parts.filter(Boolean).join("; ");
    if (joined) return joined;
  }
  if (detail && typeof detail === "object") {
    try {
      return JSON.stringify(detail);
    } catch {
      /* ignore */
    }
  }
  return `HTTP ${status}`;
}

function shortBacktestRunLabel(id: string): string {
  const t = id.trim();
  if (t.length <= 20) return t;
  return `${t.slice(0, 5)}…${t.slice(-10)}`;
}

function BacktestKpiGrid({ kpis, compact }: { kpis: BacktestKpiRow; compact?: boolean }) {
  const ddLabel =
    kpis.maxDrawdownPct > 0 && kpis.maxDrawdownPct < 0.01
      ? "<0.01%"
      : `${kpis.maxDrawdownPct.toFixed(2)}%`;
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
            <p className="font-mono text-[7px] uppercase leading-tight tracking-wider text-[var(--nexus-muted)]">
              {k.label}
            </p>
            <p className={`mt-0.5 truncate font-mono text-xs tabular-nums leading-tight ${k.tone}`}>
              {k.value}
            </p>
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
          <p className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
            {k.label}
          </p>
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
  embeddedView?: "backtest" | "research";
}) {
  const LIVE_RUN_STORAGE_KEY = "nexus_backtest_live_run_id";
  const router = useRouter();
  const { refresh: refreshDesk } = useDeskOwnership();

  const [embeddedTab, setEmbeddedTab] = useState<EmbeddedWorkspaceTab>("new");
  const [savedPane, setSavedPane] = useState<"list" | "detail">("list");

  const [strategies, setStrategies] = useState<StrategyRow[]>([]);
  const [presetId, setPresetId] = useState("macro_tilt");
  const [ticker, setTicker] = useState("BTC/USDT");
  const [dataExchange, setDataExchange] = useState<"binance" | "yahoo" | "futu">("binance");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [runPayload, setRunPayload] = useState<BacktestRunResult | null>(null);
  const [summaryPayload, setSummaryPayload] = useState<SummaryPayload | null>(null);
  const [equitySeries, setEquitySeries] = useState<EquitySeriesResponse | null>(null);
  const [tradesData, setTradesData] = useState<TradesResponse | null>(null);
  const [barsData, setBarsData] = useState<BarsResponse | null>(null);
  const [tracePayload, setTracePayload] = useState<NexusPayload | null>(null);

  const [runList, setRunList] = useState<string[]>([]);
  const [runItems, setRunItems] = useState<SavedRunListItem[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState("");
  const [jobState, setJobState] = useState<BacktestJob | null>(null);
  const [pollingJobId, setPollingJobId] = useState<string | null>(null);
  const [liveRunId, setLiveRunId] = useState<string | null>(null);
  const jobStallRef = useRef<{ step: number | null; since: number }>({ step: null, since: 0 });

  const [nBars, setNBars] = useState("220");
  const [intervalAmount, setIntervalAmount] = useState(DEFAULT_TF_AMOUNT);
  const [intervalUnit, setIntervalUnit] = useState<BarIntervalUnit>(DEFAULT_TF_UNIT);
  const [maxSteps, setMaxSteps] = useState("200");
  const [feeBps, setFeeBps] = useState("10");
  const [initialCash, setInitialCash] = useState("10000");
  const [sinceIso, setSinceIso] = useState(() => defaultDateRange(DEFAULT_LOOKBACK_DAYS).since);
  const [untilIso, setUntilIso] = useState(() => defaultDateRange(DEFAULT_LOOKBACK_DAYS).until);
  const [windowMode, setWindowMode] = useState<"latest" | "range">("range");
  const [symbolCustom, setSymbolCustom] = useState(false);

  const [historyLoading, setHistoryLoading] = useState(false);
  const [pendingReportId, setPendingReportId] = useState<string | null>(null);

  const lastUrlRunRef = useRef<string | null>(null);
  const preferNewTabRef = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const fromUrl = (initialRunId || "").trim();
    const fromStorage = window.localStorage.getItem(LIVE_RUN_STORAGE_KEY)?.trim() || "";
    const existing = fromUrl || fromStorage;
    if (!existing) return;
    if (fromStorage && (!fromUrl || fromUrl === fromStorage)) {
      setLiveRunId(fromStorage);
      setPollingJobId(fromStorage);
      setJobState({ status: "queued", step: 0, total_steps: 0 });
      lastUrlRunRef.current = fromStorage;
      preferNewTabRef.current = true;
      if (embedded) setEmbeddedTab("new");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- mount resume only
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
      .then((d: { runs?: string[]; items?: SavedRunListItem[] }) => {
        if (Array.isArray(d.items)) setRunItems(d.items);
        if (Array.isArray(d.runs)) setRunList(d.runs);
        else if (Array.isArray(d.items)) setRunList(d.items.map((x) => x.run_id));
      })
      .catch(() => {});
  }, []);

  const selected = strategies.find((s) => s.id === presetId);
  const appliedPresetDefaultsRef = useRef<string | null>(null);

  useEffect(() => {
    const sel = strategies.find((s) => s.id === presetId);
    if (!sel) return;
    if (appliedPresetDefaultsRef.current === presetId) return;
    appliedPresetDefaultsRef.current = presetId;
    setNBars(String(sel.defaults.n_bars));
    setMaxSteps(String(sel.defaults.max_steps));
    setFeeBps(String(sel.defaults.fee_bps));
    setInitialCash(String(sel.defaults.initial_cash));
    const iu = intervalSecToAmountUnit(sel.defaults.interval_sec);
    setIntervalAmount(iu.amount);
    setIntervalUnit(iu.unit);
    const days =
      typeof sel.defaults.lookback_days === "number"
        ? sel.defaults.lookback_days
        : DEFAULT_LOOKBACK_DAYS;
    const r = defaultDateRange(days);
    setWindowMode("range");
    setSinceIso(r.since);
    setUntilIso(r.until);
  }, [presetId, strategies]);

  const onSinceIsoChange = useCallback((next: string) => {
    setSinceIso(next);
    setUntilIso((prev) => (prev && next && prev < next ? next : prev));
  }, []);
  const onUntilIsoChange = useCallback((next: string) => {
    setUntilIso(next);
  }, []);

  const buildBody = useCallback(() => {
    const body: Record<string, unknown> = {
      preset_id: presetId,
      ticker,
      exchange_id: dataExchange,
    };
    if (!selected) return body;
    const nb = parseInt(nBars, 10);
    const amt = parseFloat(intervalAmount);
    const ms = parseInt(maxSteps, 10);
    const fee = parseFloat(feeBps);
    const cash = parseFloat(initialCash);
    if (!Number.isNaN(nb)) body.n_bars = nb;
    if (!Number.isNaN(amt) && amt > 0)
      body.interval_sec = amountUnitToIntervalSec(amt, intervalUnit);
    if (!Number.isNaN(ms)) body.max_steps = ms;
    if (!Number.isNaN(fee)) body.fee_bps = fee;
    if (!Number.isNaN(cash)) body.initial_cash = cash;

    const s = sinceIso.trim();
    const u = untilIso.trim();
    if (windowMode === "range" && s && u && dataExchange !== "futu") {
      body.since_iso = s;
      body.until_iso = u;
    }
    return body;
  }, [
    presetId,
    ticker,
    dataExchange,
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

  const resumeRunningJob = useCallback(
    (runId: string, job?: Partial<BacktestJob> | null) => {
      const id = runId.trim();
      if (!id) return;
      preferNewTabRef.current = true;
      lastUrlRunRef.current = id;
      setError(null);
      setLiveRunId(id);
      setPollingJobId(id);
      setJobState({
        status: (job?.status as BacktestJob["status"]) || "running",
        step: typeof job?.step === "number" ? job.step : 0,
        total_steps: typeof job?.total_steps === "number" ? job.total_steps : 0,
        trade_count: typeof job?.trade_count === "number" ? job.trade_count : undefined,
        equity: typeof job?.equity === "number" ? job.equity : undefined,
        positions: typeof job?.positions === "number" ? job.positions : undefined,
        capital: typeof job?.capital === "number" ? job.capital : undefined,
        warmup: Boolean(job?.warmup),
      });
      setLoading(true);
      if (embedded) setEmbeddedTab("new");
      if (typeof window !== "undefined") {
        window.localStorage.setItem(LIVE_RUN_STORAGE_KEY, id);
      }
    },
    [LIVE_RUN_STORAGE_KEY, embedded],
  );

  const loadHistoricalRun = useCallback(
    async (runId: string): Promise<boolean> => {
      if (!runId) return false;
      preferNewTabRef.current = false;
      setHistoryLoading(true);
      setError(null);
      try {
        const base = getFlowApiOrigin();
        // Mid-run: job.json exists before summary — resume instead of 404.
        const jRes = await fetch(`${base}/backtests/jobs/${encodeURIComponent(runId)}`);
        if (jRes.ok) {
          const job = (await jRes.json().catch(() => ({}))) as BacktestJob;
          if (job.status === "running" || job.status === "queued") {
            resumeRunningJob(runId, job);
            return true;
          }
        }
        const sRes = await fetch(`${base}/backtests/${encodeURIComponent(runId)}/summary`);
        const raw = await sRes.json().catch(() => ({}));
        if (!sRes.ok) {
          const detail =
            typeof raw.detail === "string"
              ? raw.detail
              : `Could not load run ${runId} (HTTP ${sRes.status})`;
          if (sRes.status === 404 || /unknown backtest/i.test(detail)) {
            setError(null);
            lastUrlRunRef.current = runId;
            if (embedded) {
              setEmbeddedTab("saved");
              setSavedPane("list");
            }
            return false;
          }
          setError(detail);
          return false;
        }
        lastUrlRunRef.current = runId;
        router.replace(researchConsoleHref(runId), { scroll: false });
        setJobState(null);
        setRunPayload(null);
        setSummaryPayload(raw as SummaryPayload);
        setSelectedHistoryId(runId);
        setPendingReportId(null);
        setSavedPane("detail");
        if (embedded) setEmbeddedTab("saved");
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
    [embedded, fetchSeries, fetchTracePayload, resumeRunningJob, router],
  );

  const tryLoadHistoricalRunNoUrl = useCallback(
    async (runId: string): Promise<boolean> => {
      if (!runId) return false;
      setHistoryLoading(true);
      setError(null);
      try {
        const base = getFlowApiOrigin();
        const sRes = await fetch(`${base}/backtests/${encodeURIComponent(runId)}/summary`);
        const raw = await sRes.json().catch(() => ({}));
        if (!sRes.ok) {
          return false;
        }
        lastUrlRunRef.current = runId;
        router.replace(researchConsoleHref(runId), { scroll: false });
        setJobState(null);
        setRunPayload(null);
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
    [fetchSeries, fetchTracePayload, router],
  );

  const jobRunning =
    !!pollingJobId && (jobState?.status === "running" || jobState?.status === "queued");

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
          // API restart clears in-memory jobs — hydrate from disk artifacts if present.
          if (res.status === 404) {
            setPollingJobId(null);
            setLoading(false);
            if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
            const ok = await tryLoadHistoricalRunNoUrl(pollingJobId);
            if (!ok) {
              setLiveRunId(null);
              setJobState(null);
              setError(
                "Backtest job not found (server restarted). No saved artifacts were found for that run.",
              );
            } else {
              preferNewTabRef.current = true;
              setPendingReportId(pollingJobId);
            }
            return;
          }
          setError(
            typeof j.detail === "string" ? j.detail : `Job poll failed (HTTP ${res.status})`,
          );
          return;
        }
        setJobState(j);
        const stepNum = typeof j.step === "number" ? j.step : null;
        if (j.status === "running" || j.status === "queued") {
          const prev = jobStallRef.current;
          if (stepNum !== prev.step) {
            jobStallRef.current = { step: stepNum, since: Date.now() };
          } else if (prev.since > 0 && Date.now() - prev.since > 120_000) {
            setError(
              `Still on bar ${stepNum ?? "?"} — waiting on the worker. If this never moves, the API may have restarted; click New backtest and re-run.`,
            );
          }
        } else {
          jobStallRef.current = { step: null, since: 0 };
        }
        if (j.status === "completed" && j.result) {
          setPollingJobId(null);
          setLiveRunId(null);
          setLoading(false);
          preferNewTabRef.current = true;
          if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
          setRunPayload(j.result);
          const rid = (j.result.run_id || "").trim();
          if (rid) {
            setPendingReportId(rid);
            setSelectedHistoryId(rid);
            lastUrlRunRef.current = rid;
            for (let attempt = 0; attempt < 6; attempt++) {
              if (cancelled) return;
              try {
                const sRes = await fetch(`${base}/backtests/${encodeURIComponent(rid)}/summary`);
                if (sRes.ok) {
                  const raw = (await sRes.json()) as SummaryPayload;
                  if (!cancelled) setSummaryPayload(raw);
                  break;
                }
              } catch {
                // retry
              }
              await new Promise((r) => window.setTimeout(r, 350));
            }
            if (cancelled) return;
            await fetchSeries(rid);
            await fetchTracePayload(rid, false);
            fetch(`${base}/backtests`)
              .then((r) => r.json())
              .then((d: { runs?: string[]; items?: SavedRunListItem[] }) => {
                if (cancelled) return;
                if (Array.isArray(d.items)) setRunItems(d.items);
                if (Array.isArray(d.runs)) setRunList(d.runs);
                else if (Array.isArray(d.items)) setRunList(d.items.map((x) => x.run_id));
              })
              .catch(() => {});
          }
        }
        if (j.status === "failed") {
          setPollingJobId(null);
          setLiveRunId(null);
          setLoading(false);
          setJobState(j);
          if (typeof window !== "undefined") window.localStorage.removeItem(LIVE_RUN_STORAGE_KEY);
          setError(typeof j.error === "string" ? j.error : "Backtest failed");
          lastUrlRunRef.current = pollingJobId;
          router.replace(researchConsoleHref(null), { scroll: false });
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
    if (!liveRunId) return;
    if (!loading && !jobRunning) return;
    void fetchTracePayload(liveRunId, true);
    const id = window.setInterval(() => {
      void fetchTracePayload(liveRunId, true);
    }, 850);
    return () => window.clearInterval(id);
  }, [liveRunId, loading, jobRunning, fetchTracePayload]);

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
    setPendingReportId(null);
    preferNewTabRef.current = true;
    if (embedded) setEmbeddedTab("new");

    const body = buildBody();
    const base = getFlowApiOrigin();

    try {
      const res = await fetch(`${base}/backtests/preset/async`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await res.json().catch(() => ({}))) as { run_id?: string; detail?: unknown };
      if (!res.ok) {
        setLoading(false);
        setError(formatFlowError(data.detail, res.status));
        void refreshDesk();
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
      lastUrlRunRef.current = data.run_id;
      router.replace(researchConsoleHref(data.run_id), { scroll: false });
      if (typeof window !== "undefined")
        window.localStorage.setItem(LIVE_RUN_STORAGE_KEY, data.run_id);
      void refreshDesk();
    } catch (e) {
      setLoading(false);
      setError(e instanceof Error ? e.message : "Request failed");
    }
  }, [buildBody, embedded, refreshDesk, router]);

  const clearToNewRun = useCallback(() => {
    preferNewTabRef.current = true;
    setHistoryLoading(false);
    setLoading(false);
    setRunPayload(null);
    setSummaryPayload(null);
    setEquitySeries(null);
    setTradesData(null);
    setBarsData(null);
    setTracePayload(null);
    setSelectedHistoryId("");
    setSavedPane("list");
    setPendingReportId(null);
    setError(null);
    // Keep job polling when switching Saved ↔ New
    const urlRun = initialRunId?.trim() || null;
    if (urlRun) lastUrlRunRef.current = urlRun;
    else lastUrlRunRef.current = null;
    if (embedded) setEmbeddedTab("new");
    if (!pollingJobId) {
      router.replace(researchConsoleHref(null), { scroll: false });
    }
  }, [embedded, initialRunId, pollingJobId, router]);

  useEffect(() => {
    const id = initialRunId?.trim() || null;
    if (!id) {
      if (!pollingJobId) lastUrlRunRef.current = null;
      return;
    }
    if (id === lastUrlRunRef.current) return;
    if (pollingJobId === id || jobRunning) {
      lastUrlRunRef.current = id;
      return;
    }
    if (pollingJobId) return;
    void loadHistoricalRun(id);
  }, [initialRunId, loadHistoricalRun, pollingJobId, jobRunning]);

  const metrics = runPayload?.metrics ?? summaryPayload?.metrics;
  const evaluation = runPayload?.evaluation;
  const activeRunId = runPayload?.run_id ?? summaryPayload?.run_id ?? selectedHistoryId ?? "";

  const kpis = useMemo(() => {
    if (!metrics && !summaryPayload && !equitySeries?.points?.length) return null;
    const m = metrics ?? ({} as NonNullable<typeof metrics>);
    const eq0 = equitySeries?.points?.[0]?.equity;
    const eqN = equitySeries?.points?.[equitySeries.points.length - 1]?.equity;
    const initial =
      evaluation?.initial_cash ??
      summaryPayload?.initial_cash ??
      m.initial_cash ??
      (typeof eq0 === "number" ? eq0 : NaN);
    const final =
      evaluation?.final_equity ??
      summaryPayload?.final_equity ??
      m.final_equity ??
      (typeof eqN === "number" ? eqN : NaN);
    const retPct =
      evaluation?.total_return_pct ??
      m.total_return_pct ??
      (Number.isFinite(initial) && initial > 0 && Number.isFinite(final)
        ? ((final - initial) / initial) * 100
        : 0);
    const trades =
      evaluation?.trade_count ??
      runPayload?.trade_count ??
      summaryPayload?.trade_count ??
      m.total_trades ??
      0;
    const steps =
      m.steps ??
      runPayload?.steps ??
      summaryPayload?.steps ??
      summaryPayload?.eval_bars ??
      equitySeries?.count ??
      0;
    const profitFactor = m.profit_factor ?? null;
    let winRatePct: number | null = null;
    if (typeof m.win_rate_pct === "number" && Number.isFinite(m.win_rate_pct)) {
      winRatePct = m.win_rate_pct;
    } else if (typeof m.win_rate === "number" && Number.isFinite(m.win_rate)) {
      // Fraction 0–1 from older payloads; treat >1 as already percent.
      winRatePct = m.win_rate <= 1 ? m.win_rate * 100 : m.win_rate;
      if (winRatePct === 0 && profitFactor == null && trades > 0) winRatePct = null;
    }
    let maxDrawdownPct = 0;
    if (typeof m.max_drawdown_pct === "number" && Number.isFinite(m.max_drawdown_pct)) {
      maxDrawdownPct = m.max_drawdown_pct;
    } else if (typeof m.max_drawdown === "number" && Number.isFinite(m.max_drawdown)) {
      maxDrawdownPct = m.max_drawdown <= 1 ? m.max_drawdown * 100 : m.max_drawdown;
    }
    const sharpe = typeof m.sharpe === "number" && Number.isFinite(m.sharpe) ? m.sharpe : 0;
    return {
      totalReturnPct: typeof retPct === "number" && Number.isFinite(retPct) ? retPct : 0,
      sharpe,
      maxDrawdownPct,
      winRatePct,
      profitFactor,
      trades: typeof trades === "number" ? trades : 0,
      steps: typeof steps === "number" ? steps : 0,
      finalEquity: final,
      initialCash: initial,
      intervalSec: (() => {
        const candidates = [
          m.interval_sec,
          (m as { sharpe_bar_interval_sec_used?: number }).sharpe_bar_interval_sec_used,
          summaryPayload?.interval_sec,
          summaryPayload?.bar_interval_sec_inferred,
          barsData?.interval_sec,
        ];
        for (const v of candidates) {
          if (typeof v === "number" && Number.isFinite(v) && v > 0) return v;
        }
        return null;
      })(),
    };
  }, [metrics, evaluation, runPayload, summaryPayload, equitySeries, barsData]);

  const openRunReport = useCallback(
    (runId?: string | null) => {
      const id = (runId || pendingReportId || runPayload?.run_id || selectedHistoryId || "").trim();
      if (!id) return;
      preferNewTabRef.current = false;
      setSelectedHistoryId(id);
      lastUrlRunRef.current = id;
      router.replace(researchConsoleHref(id), { scroll: false });
      if (embedded) {
        setEmbeddedTab("saved");
        setSavedPane("detail");
      }
      const localReady =
        (runPayload?.run_id === id && Boolean(runPayload.metrics || equitySeries?.points?.length)) ||
        (summaryPayload?.run_id === id);
      if (localReady) {
        setPendingReportId(null);
        if (!summaryPayload || summaryPayload.run_id !== id) {
          const base = getFlowApiOrigin();
          void fetch(`${base}/backtests/${encodeURIComponent(id)}/summary`)
            .then(async (sRes) => {
              if (!sRes.ok) return;
              const raw = (await sRes.json()) as SummaryPayload;
              setSummaryPayload(raw);
            })
            .catch(() => {});
        }
        return;
      }
      void loadHistoricalRun(id).then((ok) => {
        if (ok) setPendingReportId(null);
      });
    },
    [
      embedded,
      equitySeries?.points?.length,
      loadHistoricalRun,
      pendingReportId,
      router,
      runPayload,
      selectedHistoryId,
      summaryPayload,
    ],
  );

  const displayPayload = runPayload ?? (summaryPayload as unknown as BacktestRunResult | null);

  const tracesToShow = tracePayload?.traces ?? [];
  const messageLog = tracePayload?.message_log ?? [];
  const streamingThoughts = Boolean(jobRunning && liveRunId && embeddedTab === "new");
  const showLiveTimeline =
    embeddedTab === "new" &&
    (streamingThoughts || messageLog.length > 0 || tracesToShow.length > 0);
  const followRunLabel = (liveRunId || pollingJobId || selectedHistoryId || "").trim();
  const timelineEmptyHint = streamingThoughts
    ? jobState?.warmup
      ? "Preparing…"
      : "Waiting for the first bar…"
    : embedded && kpis && messageLog.length === 0 && tracesToShow.length === 0
      ? "No agent events for this run yet."
      : null;
  const formBusy = jobRunning || loading || historyLoading;

  const progressPct =
    jobState?.total_steps && jobState.total_steps > 0 && jobState.step != null
      ? Math.min(100, Math.round((jobState.step / jobState.total_steps) * 100))
      : 0;


  function savedRunsNewestFirst(): SavedRunListItem[] {
    const rows: SavedRunListItem[] = runItems.length
      ? [...runItems]
      : runList.map((id) => ({ run_id: id }) as SavedRunListItem);
    rows.sort((a, b) => {
      const ta =
        typeof a.sort_ts === "number" && Number.isFinite(a.sort_ts)
          ? a.sort_ts
          : Date.parse(a.end_iso || a.start_iso || "") || 0;
      const tb =
        typeof b.sort_ts === "number" && Number.isFinite(b.sort_ts)
          ? b.sort_ts
          : Date.parse(b.end_iso || b.start_iso || "") || 0;
      if (tb !== ta) return tb - ta;
      return String(b.run_id).localeCompare(String(a.run_id));
    });
    return rows;
  }

  function renderSetupForm(compactForm = false, opts?: { omitRunCta?: boolean }) {
    const lb = compactForm
      ? "block font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]"
      : "block font-mono text-[10px] uppercase tracking-widest text-[var(--nexus-muted)]";
    const inp = compactForm
      ? "mt-1 w-full rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px]"
      : "mt-2 w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 py-2.5 font-mono text-xs";
    const sel = compactForm
      ? "mt-1 w-full rounded border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-2 py-1.5 font-mono text-[11px] text-[var(--nexus-text)]"
      : "mt-2 w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)] px-3 py-2.5 font-mono text-xs text-[var(--nexus-text)]";

    const tfId = matchTimeframePreset(intervalAmount, intervalUnit);
    const cashLabel = Number(initialCash);
    const cashText = Number.isFinite(cashLabel)
      ? `$${cashLabel.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
      : "$—";
    const sourceLabel =
      dataExchange === "yahoo" ? "Yahoo Finance" : dataExchange === "futu" ? "Futu OpenD" : "Binance";
    const windowLabel =
      windowMode === "range" && sinceIso && untilIso
        ? `${sinceIso} → ${untilIso}`
        : windowMode === "latest"
          ? `Last ${nBars || "N"} candles`
          : "Pick a date range";
    const timeframeLabel = tfId ?? `${intervalAmount || "?"}${intervalUnit === "min" ? "m" : intervalUnit === "hr" ? "h" : intervalUnit === "day" ? "d" : "s"}`;

    const applyMarket = (market: "crypto" | "stocks" | "futu") => {
      const range = defaultDateRange(DEFAULT_LOOKBACK_DAYS);
      setIntervalAmount(DEFAULT_TF_AMOUNT);
      setIntervalUnit(DEFAULT_TF_UNIT);
      setSinceIso(range.since);
      setUntilIso(range.until);
      setWindowMode("range");
      if (market === "crypto") {
        setDataExchange("binance");
        setSymbolCustom(false);
        setTicker("BTC/USDT");
        return;
      }
      if (market === "stocks") {
        setDataExchange("yahoo");
        setSymbolCustom(false);
        setTicker("AAPL");
        return;
      }
      setDataExchange("futu");
      setSymbolCustom(false);
      setTicker("HK.00700");
      setWindowMode("latest");
      setSinceIso("");
      setUntilIso("");
    };

    const marketMode: "crypto" | "stocks" | "futu" =
      dataExchange === "futu" ? "futu" : dataExchange === "yahoo" ? "stocks" : "crypto";
    const symbolOptions =
      marketMode === "stocks" ? STOCK_SYMBOLS : marketMode === "crypto" ? CRYPTO_SYMBOLS : null;

    const rangeMissing =
      windowMode === "range" && dataExchange !== "futu" && (!sinceIso || !untilIso);
    const tickerOk = Boolean(ticker.trim());
    const cashOk = Number.isFinite(Number(initialCash)) && Number(initialCash) > 0;
    const canRun =
      !formBusy &&
      strategies.length > 0 &&
      Boolean(presetId) &&
      tickerOk &&
      cashOk &&
      !rangeMissing;
    const runHint = streamingThoughts
      ? jobState?.warmup
        ? "Preparing…"
        : "Running…"
      : !strategies.length
        ? "Loading strategies…"
        : !presetId
          ? "Select a strategy"
          : !tickerOk
            ? "Pick a symbol"
            : !cashOk
              ? "Enter starting capital"
              : rangeMissing
                ? "Set From and To dates"
                : "Ready";

    const runButtonClass = canRun
      ? compactForm
        ? "w-full rounded-lg bg-[var(--nexus-glow)] px-4 py-2.5 font-mono text-[11px] font-semibold uppercase tracking-wider text-[var(--nexus-bg)] transition hover:brightness-110 disabled:opacity-50"
        : "w-full rounded-xl bg-[var(--nexus-glow)] px-5 py-3 font-mono text-[12px] font-semibold uppercase tracking-widest text-[var(--nexus-bg)] shadow-[0_0_24px_rgba(0,212,170,0.2)] transition hover:brightness-110 disabled:opacity-50 sm:w-auto"
      : compactForm
        ? "w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/40 px-4 py-2.5 font-mono text-[11px] font-medium uppercase tracking-wider text-[var(--nexus-muted)] transition disabled:opacity-60"
        : "w-full rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/40 px-5 py-3 font-mono text-[12px] font-medium uppercase tracking-widest text-[var(--nexus-muted)] transition disabled:opacity-60 sm:w-auto";

    return (
      <>
        <div
          className={`sticky top-0 z-20 border-b border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/95 backdrop-blur-sm ${compactForm ? "mb-2 py-2" : "mb-4 py-3"}`}
        >
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span
              className={`inline-flex items-center gap-1.5 font-mono text-[9px] uppercase tracking-wider ${
                canRun || streamingThoughts ? "text-[var(--nexus-glow)]" : "text-[var(--nexus-muted)]"
              }`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  streamingThoughts
                    ? "animate-pulse bg-[var(--nexus-glow)]"
                    : canRun
                      ? "bg-[var(--nexus-glow)]"
                      : "bg-[var(--nexus-muted)]/45"
                }`}
                aria-hidden
              />
              {runHint}
            </span>
            <p className="min-w-0 flex-1 font-mono text-[9px] leading-snug text-[var(--nexus-muted)]">
              <span className="text-[var(--nexus-text)]">{selected?.title ?? "Strategy"}</span>
              {" · "}
              {ticker || "—"} · {timeframeLabel} · {windowLabel} · {cashText} start · {sourceLabel}
            </p>
          </div>
        </div>

        {!compactForm ? (
          <div className="mb-4 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/40 p-3">
            <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--nexus-glow)]">
              What this run does
            </p>
            <p className="mt-1 text-[12px] leading-relaxed text-[var(--nexus-muted)]">
              Agents replay historical candles for <span className="text-[var(--nexus-text)]">{ticker || "your symbol"}</span>
              {windowMode === "range" ? (
                <>
                  {" "}from <span className="text-[var(--nexus-text)]">{sinceIso || "…"}</span> to{" "}
                  <span className="text-[var(--nexus-text)]">{untilIso || "…"}</span>
                </>
              ) : (
                <> using the latest <span className="text-[var(--nexus-text)]">{nBars || "N"}</span> candles</>
              )}
              , decide trades bar-by-bar, and report PnL from a virtual{" "}
              <span className="text-[var(--nexus-text)]">{cashText}</span> starting balance.
            </p>
          </div>
        ) : null}

        <div className={`flex flex-col ${compactForm ? "gap-2" : "gap-3"}`}>
          <label className={lb}>{compactForm ? "Strategy" : "1 · Strategy"}</label>
          {strategies.length > 0 && (
            <StrategyCardSelector
              strategies={strategies}
              selectedId={presetId}
              onSelect={setPresetId}
              disabled={formBusy}
            />
          )}
          {strategies.length === 0 && (
            <div className="rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.2)] p-3 text-[10px] text-[var(--nexus-muted)]">
              Loading strategies…
            </div>
          )}
          {selected?.reasoning_preview && !compactForm ? (
            <ReasoningPreviewCard reasoning={selected.reasoning_preview} title={selected.title} />
          ) : null}
        </div>

        <div
          className={`${
            compactForm
              ? "mt-2 space-y-2.5 rounded-lg bg-[var(--nexus-surface)]/25 px-2.5 py-2.5"
              : "mt-5 space-y-4 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/35 p-3"
          }`}
        >
          <div className={`grid ${compactForm ? "grid-cols-1 gap-2 sm:grid-cols-2" : "grid-cols-1 gap-4"}`}>
            <div>
              <label className={lb}>{compactForm ? "Market" : "2 · Market"}</label>
              <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label="Market type">
                {(
                  [
                    ["crypto", "Crypto"],
                    ["stocks", "Stocks"],
                    ["futu", "Futu"],
                  ] as const
                ).map(([id, label]) => (
                  <button
                    key={id}
                    type="button"
                    disabled={formBusy}
                    onClick={() => applyMarket(id)}
                    className={`rounded-md px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ring-1 transition ${
                      marketMode === id
                        ? "bg-[rgba(34,211,238,0.14)] text-[#22d3ee] ring-[rgba(34,211,238,0.35)]"
                        : "bg-white/[0.03] text-[var(--nexus-muted)] ring-white/10 hover:text-[var(--nexus-text)]"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            <div className="min-w-0">
              <label className={lb}>{compactForm ? "Symbol" : "3 · Symbol / asset"}</label>
              {dataExchange === "futu" ? (
                <FutuTickerCombobox
                  value={ticker}
                  onChange={setTicker}
                  disabled={formBusy}
                  compact={compactForm}
                />
              ) : symbolCustom || (symbolOptions && !(symbolOptions as readonly string[]).includes(ticker)) ? (
                <div className="mt-1 space-y-1">
                  <input
                    className={inp}
                    value={ticker}
                    onChange={(e) => setTicker(e.target.value)}
                    placeholder={dataExchange === "yahoo" ? "AAPL or BTC-USD" : "BTC/USDT"}
                    disabled={formBusy}
                  />
                  <button
                    type="button"
                    className="font-mono text-[9px] text-[var(--nexus-glow)] hover:underline"
                    onClick={() => {
                      setSymbolCustom(false);
                      setTicker(marketMode === "stocks" ? "AAPL" : "BTC/USDT");
                    }}
                  >
                    Back to list
                  </button>
                </div>
              ) : (
                <select
                  className={sel}
                  value={ticker}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (v === "__custom__") {
                      setSymbolCustom(true);
                      return;
                    }
                    setTicker(v);
                  }}
                  disabled={formBusy}
                  aria-label="Symbol"
                >
                  {(symbolOptions ?? []).map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                  <option value="__custom__">Custom…</option>
                </select>
              )}
            </div>
          </div>

          <div>
            <label className={lb}>{compactForm ? "Timeframe" : "4 · Timeframe (candle size)"}</label>
            <div className="mt-1 flex flex-wrap gap-1.5" role="group" aria-label="Timeframe">
              {TIMEFRAME_PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  disabled={formBusy}
                    onClick={() => {
                      const alreadySelected = tfId === p.id;
                      setIntervalAmount(p.amount);
                      setIntervalUnit(p.unit);
                      if (alreadySelected) return;
                      if (p.unit === "day") {
                        const r = defaultDateRange(DEFAULT_LOOKBACK_DAYS);
                        setSinceIso(r.since);
                        setUntilIso(r.until);
                        setWindowMode("range");
                      } else if (p.unit === "hr") {
                        const r = defaultDateRange(DEFAULT_LOOKBACK_DAYS);
                        setSinceIso(r.since);
                        setUntilIso(r.until);
                        setWindowMode("range");
                      } else if (p.unit === "min" && Number(p.amount) <= 15) {
                        const r = defaultDateRange(7);
                        setSinceIso(r.since);
                        setUntilIso(r.until);
                        setWindowMode("range");
                      }
                    }}
                  className={`rounded-md px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider ring-1 transition ${
                    tfId === p.id
                      ? "bg-[rgba(0,212,170,0.16)] text-[var(--nexus-glow)] ring-[rgba(0,212,170,0.4)]"
                      : "bg-white/[0.03] text-[var(--nexus-muted)] ring-white/10 hover:text-[var(--nexus-text)]"
                  }`}
                >
                  {p.label}
                </button>
              ))}
            </div>
            {!compactForm ? (
              <p className="mt-1 text-[10px] text-[var(--nexus-muted)]">
                How wide each candle is. Shorter timeframes need shorter date ranges.
              </p>
            ) : null}
          </div>

          <div className={`grid grid-cols-1 ${compactForm ? "gap-2 sm:grid-cols-[1fr_9rem]" : "gap-4"}`}>
            <div
              className={`${
                compactForm
                  ? "space-y-1.5"
                  : "rounded-md border border-[color:var(--nexus-card-stroke)]/80 bg-[var(--nexus-bg)]/25 p-3"
              }`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className={lb}>{compactForm ? "Dates" : "5 · From / To dates"}</label>
                <div className="flex flex-wrap gap-1.5" role="group" aria-label="Window mode">
                  <button
                    type="button"
                    disabled={formBusy || dataExchange === "futu"}
                    onClick={() => {
                      setWindowMode("range");
                      if (!sinceIso || !untilIso) {
                        const r = defaultDateRange(DEFAULT_LOOKBACK_DAYS);
                        setSinceIso(r.since);
                        setUntilIso(r.until);
                      }
                    }}
                    className={`rounded-md px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider ring-1 ${
                      windowMode === "range"
                        ? "bg-[rgba(34,211,238,0.14)] text-[#22d3ee] ring-[rgba(34,211,238,0.35)]"
                        : "text-[var(--nexus-muted)] ring-white/10"
                    }`}
                  >
                    From / To
                  </button>
                  <button
                    type="button"
                    disabled={formBusy}
                    onClick={() => {
                      setWindowMode("latest");
                      setSinceIso("");
                      setUntilIso("");
                    }}
                    title="Advanced: fetch the most recent N candles instead of a calendar range"
                    className={`rounded-md px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider ring-1 ${
                      windowMode === "latest"
                        ? "bg-[rgba(34,211,238,0.10)] text-[#22d3ee] ring-[rgba(34,211,238,0.28)]"
                        : "text-[var(--nexus-muted)] ring-white/10"
                    }`}
                  >
                    Last N candles
                  </button>
                </div>
              </div>

              {windowMode === "range" && dataExchange !== "futu" ? (
                <div className="mt-2 w-full">
                  <div className="flex w-full flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-end sm:gap-3">
                    <div className="min-w-0 sm:w-[min(100%,12rem)]">
                      <label className={lb}>From</label>
                      <DatePickerField
                        label="From"
                        value={sinceIso}
                        onChange={onSinceIsoChange}
                        disabled={formBusy}
                        className={inp}
                        placeholder="YYYY-MM-DD"
                      />
                    </div>
                    <span
                      className="hidden select-none pb-2.5 font-mono text-[10px] text-[var(--nexus-muted)] sm:inline"
                      aria-hidden
                    >
                      →
                    </span>
                    <div className="min-w-0 sm:w-[min(100%,12rem)]">
                      <label className={lb}>To</label>
                      <DatePickerField
                        label="To"
                        value={untilIso}
                        onChange={onUntilIsoChange}
                        minIso={sinceIso || undefined}
                        disabled={formBusy}
                        className={inp}
                        placeholder="YYYY-MM-DD"
                      />
                    </div>
                  </div>
                </div>
              ) : (
                <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <div>
                    <label className={lb}>Candles to fetch</label>
                    <input
                      className={`${inp} tabular-nums`}
                      inputMode="numeric"
                      value={nBars}
                      onChange={(e) => setNBars(e.target.value)}
                      disabled={formBusy}
                    />
                  </div>
                  {dataExchange === "futu" ? (
                    <p className="self-end text-[10px] text-[var(--nexus-muted)]">
                      Futu OpenD uses latest candles (no calendar range yet).
                    </p>
                  ) : null}
                </div>
              )}
            </div>

            <div className="min-w-0">
              <label className={lb}>{compactForm ? "Start $" : "6 · Starting capital"}</label>
              <div className="relative">
                <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 font-mono text-[11px] text-[var(--nexus-muted)]">
                  $
                </span>
                <input
                  className={`${inp} pl-7 tabular-nums`}
                  inputMode="decimal"
                  value={initialCash}
                  onChange={(e) => setInitialCash(e.target.value)}
                  disabled={formBusy}
                  aria-label="Starting capital"
                />
              </div>
              {!compactForm ? (
                <p className="mt-0.5 text-[10px] text-[var(--nexus-muted)]">
                  Virtual cash the paper portfolio starts with.
                </p>
              ) : null}
            </div>
          </div>
        </div>

        {!opts?.omitRunCta ? (
          <div
            className={`border-t border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/95 ${
              compactForm ? "mt-4 px-0 py-2.5" : "sticky bottom-0 z-10 mt-5 py-3 backdrop-blur-sm"
            }`}
          >
            <div className={`flex flex-col gap-2 ${compactForm ? "" : "sm:flex-row sm:items-center"}`}>
              <button
                type="button"
                disabled={!canRun}
                onClick={() => void runPreset()}
                className={runButtonClass}
              >
                {streamingThoughts ? "Running…" : "Run backtest"}
              </button>
              <p className="min-w-0 font-mono text-[9px] leading-snug text-[var(--nexus-muted)] sm:flex-1">
                {canRun
                  ? `${selected?.title ?? "Strategy"} · ${ticker} · ${timeframeLabel} · ${windowLabel}`
                  : runHint}
              </p>
            </div>
            {(summaryPayload || runPayload) && !streamingThoughts ? (
              <button
                type="button"
                onClick={() => {
                  clearToNewRun();
                  if (embedded) setEmbeddedTab("new");
                }}
                className={
                  compactForm
                    ? "mt-2 rounded-md px-0 py-1 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-muted)] underline-offset-2 transition hover:text-[var(--nexus-text)] hover:underline"
                    : "mt-2 rounded-lg px-0 py-1 font-mono text-[11px] uppercase tracking-widest text-[var(--nexus-muted)] underline-offset-2 transition hover:text-[var(--nexus-text)] hover:underline"
                }
              >
                Configure new run
              </button>
            ) : null}
          </div>
        ) : null}

        {jobRunning && jobState ? (
          <div
            className={`space-y-1.5 ${
              compactForm
                ? "mt-3 border-t border-[color:var(--nexus-rule-soft)] pt-3"
                : "mt-4 space-y-2 rounded-lg bg-[var(--nexus-glow)]/5 p-3 ring-1 ring-[color:var(--nexus-glow)]/18"
            }`}
          >
            <div className="flex flex-wrap items-center justify-between gap-2 font-mono text-[10px] text-[var(--nexus-muted)]">
              <span className="text-[var(--nexus-glow)]">
                {jobState.warmup ? "Preparing" : "Progress"}
              </span>
              <span>
                {jobState.warmup
                  ? "0%"
                  : `${jobState.step ?? 0} / ${jobState.total_steps || "…"} · ${progressPct}%`}
              </span>
            </div>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--nexus-surface)]">
              <div
                className="h-full bg-[var(--nexus-glow)] transition-[width] duration-300"
                style={{ width: `${jobState.warmup ? 0 : progressPct}%` }}
              />
            </div>
            {!jobState.warmup ? (
              <p
                className="font-mono text-[10px] text-[var(--nexus-muted)]"
                title="Equity is mark-to-market (open positions count). Closed = finished round-trips only — an open trade can move equity with 0 closed."
              >
                {formatJobBookLine(jobState)}
              </p>
            ) : null}
          </div>
        ) : null}

        {!jobRunning && pendingReportId ? (
          <div
            className={`flex flex-wrap items-center justify-between gap-2 ${
              compactForm
                ? "mt-3 border-t border-[color:var(--nexus-rule-soft)] pt-3"
                : "mt-4 rounded-lg bg-[var(--nexus-glow)]/8 p-3 ring-1 ring-[color:var(--nexus-glow)]/22"
            }`}
          >
            <p className="font-mono text-[10px] text-[var(--nexus-glow)]">
              Finished · {shortBacktestRunLabel(pendingReportId)}
            </p>
            <button
              type="button"
              onClick={() => openRunReport(pendingReportId)}
              className="rounded-md bg-[var(--nexus-glow)] px-3 py-1.5 font-mono text-[10px] font-semibold uppercase tracking-wider text-[var(--nexus-bg)] hover:brightness-110"
            >
              View report
            </button>
          </div>
        ) : null}

        {!embedded ? (
          <p className="mt-4 text-[10px] leading-relaxed text-[var(--nexus-muted)]">
            Async job + browser polling. Set{" "}
            <code className="text-[var(--nexus-text)]">NEXT_PUBLIC_FLOW_API_BASE_URL</code> if the
            API is not on <code className="text-[var(--nexus-text)]">127.0.0.1:8001</code>.
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
            <h2 className="font-mono text-[10px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Results
            </h2>
            <BacktestKpiGrid kpis={kpis} />
          </>
        ) : (
          <>
            <h2 className="font-mono text-[9px] uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
              Performance
            </h2>
            <BacktestKpiGrid kpis={kpis} compact />
          </>
        )}

        <div className={compact ? "grid gap-2 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]" : "grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]"}>
          <div className={card}>
            <h3 className={h3}>Key metrics</h3>
            <dl className={`mt-2 space-y-1.5 font-mono ${compact ? "text-[10px]" : "text-[11px]"}`}>
              {(
                [
                  ["Initial capital", Number.isFinite(kpis.initialCash) ? `$${kpis.initialCash.toLocaleString()}` : "—"],
                  [
                    "Final equity",
                    typeof kpis.finalEquity === "number"
                      ? `$${kpis.finalEquity.toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                      : "—",
                  ],
                  [
                    "Total return",
                    `${kpis.totalReturnPct >= 0 ? "+" : ""}${kpis.totalReturnPct.toFixed(2)}%`,
                  ],
                  [
                    `${summaryPayload?.benchmark?.benchmark_symbol || barsData?.benchmark_symbol || "Benchmark"} buy&hold`,
                    typeof summaryPayload?.benchmark?.benchmark_buy_hold_equity_return_pct === "number"
                      ? `${summaryPayload.benchmark.benchmark_buy_hold_equity_return_pct >= 0 ? "+" : ""}${summaryPayload.benchmark.benchmark_buy_hold_equity_return_pct.toFixed(2)}%`
                      : "—",
                  ],
                  [
                    "Excess vs buy&hold",
                    typeof summaryPayload?.benchmark?.excess_return_vs_buy_hold_equity_pct === "number"
                      ? `${summaryPayload.benchmark.excess_return_vs_buy_hold_equity_pct >= 0 ? "+" : ""}${summaryPayload.benchmark.excess_return_vs_buy_hold_equity_pct.toFixed(2)}%`
                      : "—",
                  ],
                  ["Sharpe (ann.)", kpis.sharpe.toFixed(3)],
                  ["Max drawdown", `${kpis.maxDrawdownPct.toFixed(2)}%`],
                  ["Win rate", kpis.winRatePct == null ? "—" : `${kpis.winRatePct.toFixed(1)}%`],
                  [
                    "Profit factor",
                    kpis.profitFactor == null ? "—" : kpis.profitFactor.toFixed(2),
                  ],
                  [
                    "Commissions",
                    typeof metrics?.total_commission === "number"
                      ? `$${Number(metrics.total_commission).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                      : "—",
                  ],
                  [
                    "Total PnL",
                    typeof metrics?.total_pnl_usd === "number"
                      ? `$${Number(metrics.total_pnl_usd).toLocaleString(undefined, { maximumFractionDigits: 2 })}`
                      : "—",
                  ],
                  ["Fills", String(kpis.trades)],
                ] as const
              ).map(([label, value]) => (
                <div
                  key={label}
                  className="flex justify-between gap-3 border-b border-[color:var(--nexus-rule-soft)] pb-1.5"
                >
                  <dt className="text-[var(--nexus-muted)]">{label}</dt>
                  <dd className="text-right tabular-nums text-[var(--nexus-text)]">{value}</dd>
                </div>
              ))}
            </dl>
          </div>
          <div className={card}>
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h3 className={h3}>Equity vs benchmark</h3>
              <span className="font-mono text-[9px] text-[var(--nexus-muted)]">
                {equitySeries?.count ?? 0} pts
                {barsData?.benchmark_symbol ? ` · vs ${barsData.benchmark_symbol}` : ""}
              </span>
            </div>
            <p className={`text-[var(--nexus-muted)] ${compact ? "mb-1.5 mt-1 text-[9px]" : "mb-2 mt-1 text-[10px]"}`}>
              Strategy equity (teal) vs buy&hold (amber). Markers = fills.
            </p>
            <BacktestEquityChart
              points={equitySeries?.points ?? []}
              initialCash={kpis.initialCash}
              trades={
                tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? []
              }
              benchmark={barsData?.benchmark_equity ?? null}
              benchmarkLabel={`${barsData?.benchmark_symbol || "Benchmark"} buy&hold`}
              height={compact ? 220 : 280}
            />
          </div>
        </div>

        <div className={card}>
          <h3 className={h3}>Drawdown profile</h3>
          <p className={`text-[var(--nexus-muted)] ${compact ? "mb-1.5 mt-1 text-[9px]" : "mb-2 mt-1 text-[10px]"}`}>
            Underwater curve — peak-to-trough loss from the equity path.
          </p>
          <BacktestDrawdownChart
            points={equitySeries?.points ?? []}
            height={compact ? 140 : 180}
          />
        </div>

        <BacktestReportInsights
          summary={summaryPayload}
          trades={
            tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? []
          }
          compact={compact}
        />

        <div className={card}>
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 className={h3}>Price & trades</h3>
            <span className="font-mono text-[9px] text-[var(--nexus-muted)]">
              {barsData?.count != null ? `${barsData.count} candles` : "— candles"}
            </span>
          </div>
          <p className={`text-[var(--nexus-muted)] ${compact ? "mb-1.5 mt-1 text-[9px]" : "mb-2 mt-1 text-[10px]"}`}>
            Candles = price · arrows = fills
            {barsData?.fill_model ? ` · ${barsData.fill_model}` : ""}
          </p>
          <BacktestPriceChart
            bars={(barsData?.bars ?? []) as OhlcvBar[]}
            trades={
              tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? []
            }
            height={compact ? 240 : 300}
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
                trades={
                  tradesData?.trades ?? (evaluation?.trades_preview as TradeRow[] | undefined) ?? []
                }
                truncated={tradesData?.truncated}
                total={tradesData?.total}
                returned={tradesData?.returned}
              />
            </div>
            {kpis.trades === 0 ? (
              <p
                className={`text-[var(--nexus-muted)] ${compact ? "mt-2 text-[9px] leading-snug" : "mt-3 text-[10px] leading-relaxed"}`}
              >
                {compact
                  ? "No fills — see timeline for desk / risk detail."
                  : "No simulated fills: the combined desk signals and synthesis path likely did not yield a buy that cleared portfolio and risk rules, or position sizing was zero. Use the bar timeline to inspect each desk, the evidence board, arbitrator output, and risk guard per step."}
              </p>
            ) : null}
          </div>
          <div className={card}>
            <h3 className={h3}>Run details</h3>
            <dl
              className={`space-y-1.5 font-mono ${compact ? "mt-1.5 text-[10px]" : "mt-3 space-y-2 text-[11px]"}`}
            >
              <div className="flex justify-between gap-4 border-b border-[color:var(--nexus-rule-soft)] pb-2">
                <dt className="text-[var(--nexus-muted)]">Run ID</dt>
                <dd className="max-w-[60%] break-all text-right text-[var(--nexus-glow)]">
                  {activeRunId || "—"}
                </dd>
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
                  {typeof kpis.intervalSec === "number" && kpis.intervalSec > 0 ? (
                    <>
                      {formatIntervalHuman(kpis.intervalSec)}{" "}
                      <span className="text-[var(--nexus-muted)]">({kpis.intervalSec}s)</span>
                    </>
                  ) : (
                    <span className="text-[var(--nexus-muted)]">—</span>
                  )}
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
                <div className="text-[10px] leading-relaxed text-[var(--nexus-muted)]">
                  {evaluation.note}
                </div>
              ) : null}
            </dl>
            <div
              className={`flex flex-wrap items-center justify-end gap-1.5 ${compact ? "mt-2" : "mt-4 gap-2"}`}
            >
              <button
                type="button"
                disabled={!activeRunId}
                onClick={() => {
                  if (!activeRunId) return;
                  router.replace(researchConsoleHref(activeRunId), { scroll: false });
                  window.setTimeout(() => {
                    document.getElementById("nexus-supervisor")?.scrollIntoView({
                      behavior: "smooth",
                      block: "nearest",
                    });
                    (
                      document.getElementById("nexus-supervisor-input") as HTMLTextAreaElement | null
                    )?.focus();
                  }, 0);
                }}
                className={`rounded border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] font-mono uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40 ${
                  compact ? "px-2 py-1 text-[9px]" : "px-3 py-1.5 text-[10px]"
                }`}
              >
                Open in Supervisor →
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
                      displayPayload &&
                      downloadJson(displayPayload, `${activeRunId || "backtest"}-result.json`)
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
              if (t !== "saved") return;
              const readyId = (pendingReportId || selectedHistoryId || activeRunId || "").trim();
              if (readyId && (summaryPayload || runPayload)) {
                setSelectedHistoryId(readyId);
                setSavedPane("detail");
                return;
              }
              if (!selectedHistoryId && !activeRunId) {
                setSavedPane("list");
              }
            }}
            jobRunning={jobRunning}
            jobStep={jobState?.step ?? 0}
            jobTotal={jobState?.total_steps ?? 0}
            jobEquity={typeof jobState?.equity === "number" ? jobState.equity : null}
            jobClosed={jobState?.trade_count ?? 0}
            jobOpen={typeof jobState?.positions === "number" ? jobState.positions : 0}
            jobWarmup={Boolean(jobState?.warmup)}
            onResumeRunning={() => setEmbeddedTab("new")}
            reportReady={Boolean(pendingReportId) && !jobRunning}
            onOpenReport={() => openRunReport(pendingReportId)}
            savedDetailOpen={embeddedTab === "saved" && savedPane === "detail"}
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
                {embeddedTab === "saved" && savedPane === "list" ? (
                  <section className="flex flex-col gap-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                        Saved runs · recent → oldest
                      </h2>
                      <button
                        type="button"
                        disabled={
                          historyLoading ||
                          savedRunsNewestFirst().filter((r) => r.has_charts !== false).length === 0
                        }
                        onClick={() => {
                          const rows = savedRunsNewestFirst();
                          const latest =
                            rows.find((r) => r.has_charts !== false) ?? rows[0];
                          if (latest) void loadHistoricalRun(latest.run_id);
                        }}
                        className="rounded border border-[color:var(--nexus-card-stroke)] px-2 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:border-[var(--nexus-glow)]/35 hover:text-[var(--nexus-text)] disabled:opacity-40"
                      >
                        Latest complete
                      </button>
                    </div>
                    {runItems.length === 0 && runList.length === 0 ? (
                      <p className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/40 px-3 py-3 font-mono text-[10px] text-[var(--nexus-muted)]">
                        No saved runs yet — finish a New backtest to populate this list.
                      </p>
                    ) : (
                      <div className="space-y-1.5">
                        {savedRunsNewestFirst().map((r) => {
                            const ret = r.total_return_pct;
                            const retTone =
                              typeof ret === "number"
                                ? ret >= 0
                                  ? "text-[var(--nexus-success)]"
                                  : "text-[var(--nexus-danger)]"
                                : "text-[var(--nexus-muted)]";
                            const thin = r.has_charts === false;
                            return (
                              <button
                                key={r.run_id}
                                type="button"
                                disabled={historyLoading}
                                onClick={() => void loadHistoricalRun(r.run_id)}
                                className={`w-full rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/35 px-2.5 py-2 text-left transition hover:border-[rgba(138,149,166,0.4)] ${
                                  thin ? "opacity-70" : ""
                                }`}
                              >
                                <div className="flex flex-wrap items-baseline justify-between gap-x-2">
                                  <span
                                    className="font-mono text-[10px] text-[var(--nexus-text)]"
                                    title={r.run_id}
                                  >
                                    {shortBacktestRunLabel(r.run_id)}
                                  </span>
                                  <span className={`font-mono text-[10px] tabular-nums ${retTone}`}>
                                    {typeof ret === "number"
                                      ? `${ret >= 0 ? "+" : ""}${ret.toFixed(2)}%`
                                      : "—"}
                                  </span>
                                </div>
                                <div className="mt-1 flex flex-wrap gap-x-2 font-mono text-[9px] text-[var(--nexus-muted)]">
                                  <span>{r.ticker || "—"}</span>
                                  {r.start_iso || r.end_iso ? (
                                    <span>
                                      · {(r.start_iso || "").replace("T", " ").slice(0, 16)}
                                      {r.end_iso
                                        ? ` → ${(r.end_iso || "").replace("T", " ").slice(0, 16)}`
                                        : ""}
                                    </span>
                                  ) : null}
                                  {typeof r.total_trades === "number" ? (
                                    <span>· {r.total_trades} fills</span>
                                  ) : null}
                                  {typeof r.eval_bars === "number" ? (
                                    <span>· {r.eval_bars} bars</span>
                                  ) : null}
                                  {thin ? (
                                    <span className="text-amber-300/90">· incomplete</span>
                                  ) : null}
                                </div>
                              </button>
                            );
                          })}
                      </div>
                    )}
                  </section>
                ) : null}

                {embeddedTab === "saved" && savedPane === "detail" ? (
                  <div className="flex w-full max-w-none flex-col gap-3">
                    <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/95 py-1.5 backdrop-blur-sm">
                      <button
                        type="button"
                        onClick={() => {
                          setSavedPane("list");
                          preferNewTabRef.current = true;
                        }}
                        className="inline-flex items-center gap-1 rounded-md border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/80 px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-text)] hover:border-[var(--nexus-glow)]/40"
                      >
                        ← Back
                      </button>
                      <div className="min-w-0 flex-1 font-mono text-[10px] text-[var(--nexus-muted)]">
                        <span className="text-[var(--nexus-glow)]" title={activeRunId}>
                          {shortBacktestRunLabel(activeRunId || selectedHistoryId)}
                        </span>
                        {summaryPayload?.start_iso ? (
                          <span>
                            {" "}
                            · {(summaryPayload.start_iso || "").slice(0, 10)}
                            {summaryPayload.end_iso
                              ? ` → ${summaryPayload.end_iso.slice(0, 10)}`
                              : ""}
                          </span>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        onClick={() => void copyText(activeRunId || selectedHistoryId)}
                        className="rounded border border-[color:var(--nexus-card-stroke)] px-2 py-1 font-mono text-[9px] uppercase text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
                      >
                        Copy id
                      </button>
                    </div>
                    {historyLoading ? (
                      <p className="font-mono text-[10px] text-[var(--nexus-glow)] animate-pulse">
                        Loading statistical report…
                      </p>
                    ) : kpis ? (
                      <section className="flex flex-col gap-3">
                        <div className="min-w-0 shrink-0">{renderResultsDetail("embedded")}</div>
                        <section id="backtest-timeline" className="flex flex-col gap-3">
                          <h2 className="shrink-0 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                            Agent timeline
                          </h2>
                          <div className="mt-1.5 rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/30 p-1">
                            <BacktestBarTimeline
                              entries={messageLog}
                              traces={tracesToShow}
                              streaming={streamingThoughts}
                              emptyHint={timelineEmptyHint}
                              compact
                              className="max-h-[min(70vh,920px)] min-h-[200px] w-full text-[10px]"
                            />
                          </div>
                        </section>
                      </section>
                    ) : (
                      <p className="font-mono text-[10px] text-[var(--nexus-muted)]">
                        No report for this run yet.
                      </p>
                    )}
                  </div>
                ) : null}

                {embeddedTab === "new" ? (
                  <section
                    id="backtest-setup"
                    className="scroll-mt-1 flex min-h-0 flex-1 flex-col rounded-xl bg-[var(--nexus-panel)]/50 p-3"
                  >
                    <div className="min-h-0 flex-1 overflow-y-auto px-0.5 pb-8">
                      {renderSetupForm(true)}
                      {showLiveTimeline ? (
                        <section
                          id="backtest-live-timeline"
                          className="mt-4 border-t border-[color:var(--nexus-rule-soft)] pt-3"
                        >
                          <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
                            <h2 className="font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
                              Agent timeline
                            </h2>
                            {followRunLabel ? (
                              <span
                                className="font-mono text-[9px] text-[var(--nexus-glow)]"
                                title={followRunLabel}
                              >
                                {shortBacktestRunLabel(followRunLabel)}
                                {jobRunning && jobState?.total_steps
                                  ? ` · ${jobState.step ?? 0}/${jobState.total_steps}`
                                  : ""}
                              </span>
                            ) : null}
                          </div>
                          <div className="mt-1.5 flex min-h-[min(42vh,480px)] flex-col overflow-hidden rounded-lg border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-bg)]/30">
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
                    </div>
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
                Replays the full LangGraph once per OHLCV bar. Traces use the same FlowEvent
                contract as live runs: perception desks, evidence board + arbitration, risk guard,
                and execution — with structured reasoning visible in the timeline.
              </p>
            </div>
          </div>
        </header>
      ) : null}

      <div className={embedded ? "hidden" : "mx-auto max-w-6xl space-y-6 px-4 py-8"}>
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
                      {savedRunsNewestFirst().map((r) => (
                        <option key={r.run_id} value={r.run_id} title={r.run_id}>
                          {shortBacktestRunLabel(r.run_id)}
                          {r.end_iso ? ` · ${r.end_iso.slice(0, 10)}` : ""}
                        </option>
                      ))}
                    </select>
                  ) : (
                    <span className="font-mono text-[11px] text-[var(--nexus-muted)]">
                      No saved runs
                    </span>
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
                      router.replace(
                        `/console?view=research&run=${encodeURIComponent(activeRunId)}`,
                        { scroll: false },
                      );
                      window.setTimeout(() => {
                        document.getElementById("nexus-supervisor")?.scrollIntoView({
                          behavior: "smooth",
                          block: "nearest",
                        });
                        (
                          document.getElementById(
                            "nexus-supervisor-input",
                          ) as HTMLTextAreaElement | null
                        )?.focus();
                      }, 0);
                    }}
                    className="h-9 rounded-lg border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
                  >
                    Open in Supervisor →
                  </button>
                </div>
              </div>
            </section>

            <section
              id="backtest-setup"
              className="scroll-mt-4 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/80 p-5 shadow-[0_0_24px_rgba(0,212,170,0.06)]"
            >
              <div className="max-h-[calc(100vh-18rem)] overflow-y-auto pr-1">
                {renderSetupForm()}
              </div>
            </section>

            {error ? (
              <div className="rounded-lg border border-red-900/50 bg-red-950/35 px-4 py-3 font-mono text-xs text-red-100">
                {error}
              </div>
            ) : null}

            {kpis || streamingThoughts || tracesToShow.length > 0 || messageLog.length > 0 ? (
              <section className="grid w-full grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
                <div className="min-w-0 space-y-4 max-h-[calc(100vh-16rem)] overflow-y-auto">
                  <div className="min-w-0">{kpis ? renderResultsDetail("standalone") : null}</div>

                  <section className="flex min-h-[320px] w-full flex-col overflow-hidden rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
                    <div className="shrink-0 space-y-2 border-b border-[color:var(--nexus-rule-soft)] px-3 py-2">
                      <div className="min-w-0 flex-1">
                        <h3 className="text-[10px] font-semibold uppercase tracking-[0.2em] text-[var(--nexus-muted)]">
                          Bar timeline
                        </h3>
                        <p className="mt-0.5 text-[10px] leading-relaxed text-[var(--nexus-muted)]">
                          Expand a bar: chain-of-thought and event log use two columns when the
                          panel is wide enough.
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

                <aside className="flex min-h-0 flex-col gap-4 max-h-[calc(100vh-16rem)] overflow-y-auto">
                  <section className="shrink-0 rounded-xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/70 p-4 shadow-[0_0_24px_rgba(0,212,170,0.04)]">
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
                                  ? kpis.finalEquity.toLocaleString(undefined, {
                                      maximumFractionDigits: 2,
                                    })
                                  : "—"}
                              </span>
                              .{" "}
                              {typeof kpis.maxDrawdownPct === "number" ? (
                                <>
                                  Max DD{" "}
                                  <span className="font-mono">
                                    {kpis.maxDrawdownPct.toFixed(2)}%
                                  </span>
                                  .
                                </>
                              ) : null}
                            </>
                          ) : (
                            <span className="text-[var(--nexus-muted)]">
                              Run data will appear here.
                            </span>
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
                          router.replace(
                            `/console?view=research&run=${encodeURIComponent(activeRunId)}`,
                            { scroll: false },
                          );
                          window.setTimeout(() => {
                            document.getElementById("nexus-supervisor")?.scrollIntoView({
                              behavior: "smooth",
                              block: "nearest",
                            });
                            (
                              document.getElementById(
                                "nexus-supervisor-input",
                              ) as HTMLTextAreaElement | null
                            )?.focus();
                          }, 0);
                        }}
                        className="h-9 rounded-lg border border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.10)] px-3 font-mono text-[10px] uppercase tracking-wider text-[var(--nexus-glow)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
                      >
                        Open in Supervisor →
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
