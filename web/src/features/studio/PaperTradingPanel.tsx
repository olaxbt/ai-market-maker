"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { listStrategies, type SavedStrategy } from "@/lib/strategyStorage";
import { simulateForward, loadPaperState, resetPaperState, type ForwardPaperState } from "@/lib/paperForwardEngine";
import { Play, Square, RotateCcw, TrendingUp, TrendingDown, DollarSign, Activity } from "lucide-react";

const BAR_INTERVAL_OPTS = [
  { label: "1h", sec: 3600 },
  { label: "4h", sec: 14400 },
  { label: "1d", sec: 86400 },
];

export default function PaperTradingPanel() {
  const [selectedStrategy, setSelectedStrategy] = useState<SavedStrategy | null>(null);
  const [barIntervalSec, setBarIntervalSec] = useState(14400); // 4h default
  const [isRunning, setIsRunning] = useState(false);
  const [state, setState] = useState<ForwardPaperState | null>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);
  const autoRefreshRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const strategies = useMemo(() => listStrategies(), []);

  useEffect(() => {
    if (!selectedStrategy) return;
    const existing = loadPaperState(selectedStrategy.id);
    if (existing) {
      setState(existing);
      setTrades(existing.trades);
    }
  }, [selectedStrategy]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [log]);

  const appendLog = useCallback((msg: string) => {
    setLog((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }, []);

  const startForwardTest = useCallback(async () => {
    if (!selectedStrategy) return;
    setIsRunning(true);
    setError(null);
    appendLog(`Starting forward test: ${selectedStrategy.name}`);

    try {
      const tf = barIntervalSec === 3600 ? "1h" : barIntervalSec === 14400 ? "4h" : "1d";
      const res = await fetch(
        `/api/studio/price?symbol=${encodeURIComponent(selectedStrategy.config.ticker)}&interval=${tf}&limit=500`,
      );
      if (!res.ok) throw new Error(`Price API returned ${res.status}`);
      const data = await res.json();
      const bars: number[][] = data.bars;

      if (!bars || bars.length < 10) {
        throw new Error(`Not enough bars: got ${bars?.length ?? 0}`);
      }

      appendLog(`Fetched ${bars.length} bars for ${selectedStrategy.config.ticker}`);
      appendLog(`Starting forward simulation with agent config…`);

      const { state: newState, newTrades } = simulateForward(selectedStrategy, bars);

      if (newTrades.length > 0) {
        appendLog(`${newTrades.length} new trade(s) executed`);
        for (const t of newTrades) {
          appendLog(`${t.side.toUpperCase()} ${t.qty.toFixed(4)} @ ${t.price.toFixed(2)} (PnL: ${t.realizedPnlUsdt.toFixed(2)})`);
        }
      } else {
        appendLog(`No new trades — already synced through bar ${newState.barCount}`);
      }

      setState(newState);
      setTrades(newState.trades);
    } catch (err: any) {
      setError(err.message);
      appendLog(`❌ Error: ${err.message}`);
    } finally {
      setIsRunning(false);
    }
  }, [selectedStrategy, barIntervalSec, appendLog]);

  const startAutoRefresh = useCallback(() => {
    if (autoRefreshRef.current) return;
    autoRefreshRef.current = setInterval(() => {
      void startForwardTest();
    }, 60000);
    appendLog("Auto-refresh enabled (60s)");
  }, [startForwardTest, appendLog]);

  const stopAutoRefresh = useCallback(() => {
    if (autoRefreshRef.current) {
      clearInterval(autoRefreshRef.current);
      autoRefreshRef.current = null;
    }
    appendLog("Auto-refresh stopped");
  }, [appendLog]);

  const handleReset = useCallback(() => {
    if (!selectedStrategy) return;
    resetPaperState(selectedStrategy.id);
    setState(null);
    setTrades([]);
    setLog([]);
    setError(null);
    stopAutoRefresh();
    appendLog("Paper state reset");
  }, [selectedStrategy, stopAutoRefresh, appendLog]);

  useEffect(() => {
    return () => {
      if (autoRefreshRef.current) clearInterval(autoRefreshRef.current);
    };
  }, []);

  /* ── Derived metrics ── */
  const totalReturn = state ? ((state.currentEquity - state.startingEquity) / state.startingEquity) * 100 : 0;
  const openPositions = state?.positions ?? [];
  const posValue = state
    ? openPositions.reduce((sum, p) => sum + p.qty * state.currentPrice, 0)
    : 0;
  const unrealizedPnl = openPositions.reduce(
    (sum, p) => sum + (state!.currentPrice - p.avgEntry) * p.qty,
    0,
  );
  const totalRealizedPnl = state?.trades.reduce((sum, t) => sum + (t.realizedPnlUsdt ?? 0), 0) ?? 0;

  return (
    <div className="flex h-full flex-col overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[rgba(138,149,166,0.10)] px-6 py-3">
        <div className="flex items-center gap-4">
          <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">
            Paper Trading
          </div>

          {/* Strategy selector */}
          <select
            value={selectedStrategy?.id ?? ""}
            onChange={(e) => {
              const s = strategies.find((s) => s.id === e.target.value);
              setSelectedStrategy(s ?? null);
              setState(null);
              setTrades([]);
              setLog([]);
              setError(null);
            }}
            className="rounded-lg border border-[rgba(138,149,166,0.15)] bg-[rgba(6,8,11,0.4)] px-3 py-1.5 text-[11px] text-white outline-none"
          >
            <option value="">Select strategy…</option>
            {strategies.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>

          {/* Bar interval */}
          <div className="flex gap-1">
            {BAR_INTERVAL_OPTS.map((iv) => (
              <button
                key={iv.sec}
                onClick={() => setBarIntervalSec(iv.sec)}
                className={`rounded-lg px-2 py-1 text-[10px] font-medium ${
                  barIntervalSec === iv.sec
                    ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]"
                    : "text-[rgba(138,149,166,0.5)] hover:text-white"
                }`}
              >
                {iv.label}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => void startForwardTest()}
            disabled={isRunning || !selectedStrategy}
            className="flex items-center gap-1.5 rounded-xl border border-[rgba(0,212,170,0.2)] bg-[rgba(0,212,170,0.08)] px-3 py-1.5 text-[10px] font-medium text-[rgba(0,212,170,0.9)] hover:bg-[rgba(0,212,170,0.14)] disabled:opacity-40"
          >
            <Play className="h-3 w-3" />
            {isRunning ? "Running…" : "Run Now"}
          </button>
          <button
            onClick={startAutoRefresh}
            disabled={!selectedStrategy}
            className="flex items-center gap-1.5 rounded-xl border border-[rgba(99,102,241,0.2)] bg-[rgba(99,102,241,0.08)] px-3 py-1.5 text-[10px] font-medium text-[rgba(99,102,241,0.85)] hover:bg-[rgba(99,102,241,0.14)] disabled:opacity-40"
          >
            <Activity className="h-3 w-3" />
            Auto
          </button>
          <button
            onClick={stopAutoRefresh}
            className="flex items-center gap-1.5 rounded-xl border border-[rgba(242,92,84,0.15)] px-3 py-1.5 text-[10px] text-[rgba(242,92,84,0.7)] hover:border-[rgba(242,92,84,0.3)]"
          >
            <Square className="h-3 w-3" />
            Stop
          </button>
          <button
            onClick={handleReset}
            className="flex items-center gap-1.5 rounded-xl border border-[rgba(138,149,166,0.12)] px-3 py-1.5 text-[10px] text-[rgba(138,149,166,0.5)] hover:border-[rgba(138,149,166,0.25)] hover:text-white"
          >
            <RotateCcw className="h-3 w-3" />
            Reset
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: metrics + positions */}
        <div className="flex w-1/2 flex-col overflow-y-auto border-r border-[rgba(138,149,166,0.10)] p-4 space-y-4">
          {!selectedStrategy ? (
            <div className="flex h-full items-center justify-center text-[11px] text-[rgba(138,149,166,0.4)]">
              Select a saved strategy to begin paper trading
            </div>
          ) : (
            <>
              {/* KPI cards */}
              <div className="grid grid-cols-4 gap-2">
                <KpiCard
                  icon={<DollarSign className="h-3.5 w-3.5" />}
                  label="Equity"
                  value={`$${(state?.currentEquity ?? selectedStrategy.config.initial_cash).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`}
                  color="text-white"
                />
                <KpiCard
                  icon={<TrendingUp className="h-3.5 w-3.5" />}
                  label="Return"
                  value={`${totalReturn >= 0 ? "+" : ""}${totalReturn.toFixed(2)}%`}
                  color={totalReturn >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"}
                />
                <KpiCard
                  icon={<Activity className="h-3.5 w-3.5" />}
                  label="Trades"
                  value={String(state?.trades.length ?? 0)}
                  color="text-white"
                />
                <KpiCard
                  icon={<TrendingDown className="h-3.5 w-3.5" />}
                  label="Bars"
                  value={String(state?.barCount ?? 0)}
                  color="text-white"
                />
              </div>

              {/* PnL cards */}
              <div className="grid grid-cols-2 gap-2">
                <div className="rounded-xl border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.3)] px-3 py-2">
                  <div className="text-[9px] text-[rgba(138,149,166,0.5)]">Unrealized PnL</div>
                  <div className={`mt-0.5 text-[13px] font-bold tabular-nums ${unrealizedPnl >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"}`}>
                    {unrealizedPnl >= 0 ? "+" : ""}${unrealizedPnl.toFixed(2)}
                  </div>
                </div>
                <div className="rounded-xl border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.3)] px-3 py-2">
                  <div className="text-[9px] text-[rgba(138,149,166,0.5)]">Realized PnL</div>
                  <div className={`mt-0.5 text-[13px] font-bold tabular-nums ${totalRealizedPnl >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"}`}>
                    {totalRealizedPnl >= 0 ? "+" : ""}${totalRealizedPnl.toFixed(2)}
                  </div>
                </div>
              </div>

              {/* Equity curve */}
              {state && state.equityCurve.length >= 3 && (
                <div className="rounded-xl border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.3)] p-3">
                  <div className="mb-2 text-[9px] text-[rgba(138,149,166,0.5)]">Equity Curve</div>
                  <div className="h-[120px]">
                    <MiniEquityCurve points={state.equityCurve} />
                  </div>
                </div>
              )}

              {/* Open Positions */}
              <div>
                <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">
                  Open Positions ({openPositions.length})
                </div>
                {openPositions.length === 0 ? (
                  <div className="text-[11px] text-[rgba(138,149,166,0.4)] italic">No open positions</div>
                ) : (
                  <div className="space-y-1">
                    {openPositions.map((p, i) => (
                      <div key={i} className="flex items-center justify-between rounded-lg border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.25)] px-3 py-2">
                        <div>
                          <div className="text-[11px] font-semibold text-white">{p.symbol}</div>
                          <div className="text-[9px] text-[rgba(138,149,166,0.5)]">
                            {p.qty.toFixed(4)} @ ${p.avgEntry.toFixed(2)}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-[11px] font-bold text-white">${(p.qty * (state?.currentPrice ?? 0)).toFixed(2)}</div>
                          <div className={`text-[9px] ${((state?.currentPrice ?? 0) - p.avgEntry) >= 0 ? "text-[rgba(0,212,170,0.8)]" : "text-[rgba(242,92,84,0.8)]"}`}>
                            {(((state?.currentPrice ?? 0) - p.avgEntry) / p.avgEntry * 100).toFixed(2)}%
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {error && (
                <div className="rounded-xl border border-[rgba(242,92,84,0.2)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.9)]">
                  {error}
                </div>
              )}
            </>
          )}
        </div>

        {/* Right: trades + console */}
        <div className="flex w-1/2 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4">
            <div className="mb-3 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">
              Trade Log ({trades.length})
            </div>
            {trades.length === 0 ? (
              <div className="flex items-center justify-center h-32 text-[11px] text-[rgba(138,149,166,0.3)] italic">
                No trades yet — run a forward test
              </div>
            ) : (
              <div className="space-y-1">
                {trades.slice(-100).reverse().map((t, i) => (
                  <div key={i} className="flex items-start gap-3 rounded-lg border border-[rgba(138,149,166,0.06)] bg-[rgba(6,8,11,0.2)] px-3 py-2">
                    <div className={`shrink-0 rounded-full px-1.5 py-0.5 text-[9px] font-bold ${
                      t.side === "buy"
                        ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]"
                        : "bg-[rgba(242,92,84,0.12)] text-[rgba(242,92,84,0.9)]"
                    }`}>
                      {t.side.toUpperCase()}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-[rgba(226,232,240,0.75)]">
                        {t.qty.toFixed(4)} @ ${t.price.toFixed(2)}
                      </div>
                      <div className="text-[9px] text-[rgba(138,149,166,0.45)]">
                        {t.reason} · {new Date(t.ts).toLocaleString()}
                      </div>
                    </div>
                    <div className={`shrink-0 text-[10px] font-bold tabular-nums ${
                      t.realizedPnlUsdt >= 0
                        ? "text-[rgba(0,212,170,0.8)]"
                        : t.realizedPnlUsdt < 0
                          ? "text-[rgba(242,92,84,0.8)]"
                          : "text-[rgba(138,149,166,0.4)]"
                    }`}>
                      {t.realizedPnlUsdt !== 0 ? `${t.realizedPnlUsdt >= 0 ? "+" : ""}$${t.realizedPnlUsdt.toFixed(2)}` : "—"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Console */}
          <div className="border-t border-[rgba(138,149,166,0.10)] bg-[rgba(0,0,0,0.35)]">
            <div className="flex items-center justify-between px-4 py-1.5">
              <span className="text-[9px] tracking-[0.12em] text-[rgba(138,149,166,0.4)]">CONSOLE</span>
              <button onClick={() => setLog([])} className="text-[9px] text-[rgba(138,149,166,0.35)] hover:text-white">Clear</button>
            </div>
            <div className="h-[120px] overflow-y-auto px-4 pb-2 font-mono text-[10px] text-[rgba(138,149,166,0.55)] leading-[1.6]">
              {log.length === 0 ? (
                <div className="text-[rgba(138,149,166,0.25)] italic">Ready</div>
              ) : (
                log.map((msg, i) => <div key={i}>{msg}</div>)
              )}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Sub-components ── */

function KpiCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.3)] px-3 py-2">
      <div className="flex items-center gap-1.5 text-[rgba(138,149,166,0.5)]">
        {icon}
        <span className="text-[9px]">{label}</span>
      </div>
      <div className={`mt-1 text-[13px] font-bold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function MiniEquityCurve({ points }: { points: { ts: number; equity: number }[] }) {
  if (points.length < 2) return null;

  const values = points.map((p) => p.equity);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const w = 600;
  const h = 120;
  const step = w / (points.length - 1);

  const d = points
    .map((p, i) => {
      const x = i * step;
      const y = h - ((p.equity - min) / range) * (h - 8) - 4;
      return `${i === 0 ? "M" : "L"}${x},${y}`;
    })
    .join(" ");

  const color = values[values.length - 1] >= values[0]
    ? "rgba(0,212,170,0.85)"
    : "rgba(242,92,84,0.85)";

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-full w-full" preserveAspectRatio="none">
      <path d={d} stroke={color} strokeWidth="2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
