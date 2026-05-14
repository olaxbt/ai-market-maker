/**
 * Frontend paper (forward test) engine.
 *
 * Takes a strategy config + price bars, simulates allocation decisions
 * against a PaperAccount (spot mode), and produces an equity curve + trade log.
 *
 * All state lives in localStorage so it survives page refreshes.
 */

import type { SavedStrategy } from "@/lib/strategyStorage";

/* ── Types ── */

export interface PaperPosition {
  symbol: string;
  qty: number;
  avgEntry: number;
}

export interface PaperTrade {
  ts: number;
  symbol: string;
  side: "buy" | "sell";
  qty: number;
  price: number;
  notionalUsdt: number;
  feeUsdt: number;
  realizedPnlUsdt: number;
  cashUsdtAfter: number;
  reason: string;
}

export interface ForwardPaperState {
  strategyId: string;
  cashUsdt: number;
  positions: PaperPosition[];
  trades: PaperTrade[];
  startingEquity: number;
  currentEquity: number;
  equityCurve: { ts: number; equity: number }[];
  startedAt: string;
  updatedAt: string;
  barCount: number;
  currentPrice: number;
}

interface StrategyConfig {
  ticker: string;
  interval_sec: number;
  n_bars: number;
  fee_bps: number;
  initial_cash: number;
  agent_ids: string[];
  description: string;
}

/* ── Simple forward simulation ── */

/**
 * Run a forward paper simulation over price bars.
 *
 * Simulates a simple agent-weighted allocation:
 * - Agent signals are mocked based on price action (MA crossover for demo)
 * - Position sizing: each active agent votes, majority determines direction
 * - Spot mode: full cash per trade
 * - 10% per-trade risk
 */
export function simulateForward(
  strategy: SavedStrategy,
  bars: number[][],  // [ts_ms, open, high, low, close, volume][]
): { state: ForwardPaperState; newTrades: PaperTrade[] } {
  const config: StrategyConfig = strategy.config as any;
  const feeRate = (config.fee_bps ?? 5) / 10_000;
  const cash = config.initial_cash ?? 10_000;
  const agentCount = config.agent_ids.length || 1;

  // Load existing state
  const existing = loadPaperState(strategy.id);
  const startBar = existing && existing.updatedAt ? existing.barCount : 0;

  // We only process new bars
  const newBars = bars.slice(startBar);
  if (newBars.length < 2) {
    return { state: existing!, newTrades: [] };
  }

  let state = existing
    ? { ...existing, positions: [...existing.positions], trades: [...existing.trades], equityCurve: [...existing.equityCurve] }
    : createInitialState(strategy.id, cash, bars[0]);

  const newTrades: PaperTrade[] = [];

  for (let i = 0; i < newBars.length; i++) {
    const bar = newBars[i];
    const ts = Math.floor(bar[0]);
    const open = bar[1];
    const close = bar[4];
    const prevBar = i > 0 ? newBars[i - 1] : (i + startBar > 0 ? bars[i + startBar - 1] : null);

    state.currentPrice = close;
    state.barCount = startBar + i;

    // Simulate agent decision every bar
    if (prevBar) {
      const signal = computeSignal(prevBar, bar, agentCount);
      const currentPos = state.positions.find((p) => p.symbol === config.ticker);

      if (signal > 0.3 && (!currentPos || currentPos.qty <= 0)) {
        // Buy signal
        const availableCash = state.cashUsdt * 0.1; // 10% per trade
        const qty = availableCash / close;
        const fee = qty * close * feeRate;
        const totalCost = qty * close + fee;

        if (state.cashUsdt >= totalCost && qty > 0.000001) {
          state.cashUsdt -= totalCost;
          if (currentPos) {
            currentPos.qty += qty;
            currentPos.avgEntry = (currentPos.avgEntry * (currentPos.qty - qty) + close * qty) / currentPos.qty;
          } else {
            state.positions.push({ symbol: config.ticker, qty, avgEntry: close });
          }
          newTrades.push({
            ts, symbol: config.ticker, side: "buy", qty, price: close,
            notionalUsdt: qty * close, feeUsdt: fee,
            realizedPnlUsdt: 0, cashUsdtAfter: state.cashUsdt,
            reason: "Signal buy",
          });
        }
      } else if (signal < -0.3 && currentPos && currentPos.qty > 0) {
        // Sell signal
        const qty = currentPos.qty;
        const proceeds = qty * close;
        const fee = proceeds * feeRate;
        const pnl = (close - currentPos.avgEntry) * qty;
        state.cashUsdt += proceeds - fee;
        state.positions = state.positions.filter((p) => p.symbol !== config.ticker);
        newTrades.push({
          ts, symbol: config.ticker, side: "sell", qty, price: close,
          notionalUsdt: proceeds, feeUsdt: fee,
          realizedPnlUsdt: pnl, cashUsdtAfter: state.cashUsdt,
          reason: "Signal sell",
        });
      }
    }

    // Record equity
    const posValue = state.positions.reduce((sum, p) => sum + p.qty * close, 0);
    const totalEquity = state.cashUsdt + posValue;
    state.equityCurve.push({ ts, equity: totalEquity });
    state.currentEquity = totalEquity;
  }

  state.updatedAt = new Date().toISOString();
  state.trades = [...state.trades, ...newTrades];
  savePaperState(state);
  return { state, newTrades };
}

/* ── Signal mock (will be replaced by real agent delegation) ── */

function computeSignal(
  prevBar: number[],
  currBar: number[],
  _agentCount: number,
): number {
  const prevClose = prevBar[4];
  const currClose = currBar[4];

  // Simple momentum + volume confirmation
  const priceChange = (currClose - prevClose) / prevClose;
  const prevVol = prevBar[5];
  const currVol = currBar[5];
  const volRatio = prevVol > 0 ? currVol / prevVol : 1;

  let signal = priceChange * 10;  // scale to ~ -1 to 1 range
  if (volRatio > 1.5 && priceChange > 0) signal *= 1.3;  // volume confirmation
  if (volRatio > 1.5 && priceChange < 0) signal *= 1.3;  // volume confirmation on sell

  return Math.max(-1, Math.min(1, signal));
}

/* ── State persistence (localStorage) ── */

const STATE_KEY_PREFIX = "aimm_paper_";

function createInitialState(
  strategyId: string,
  cash: number,
  firstBar: number[],
): ForwardPaperState {
  return {
    strategyId,
    cashUsdt: cash,
    positions: [],
    trades: [],
    startingEquity: cash,
    currentEquity: cash,
    equityCurve: [{ ts: Math.floor(firstBar[0]), equity: cash }],
    startedAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    barCount: 0,
    currentPrice: firstBar[4],
  };
}

export function loadPaperState(strategyId: string): ForwardPaperState | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(STATE_KEY_PREFIX + strategyId);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function savePaperState(state: ForwardPaperState): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STATE_KEY_PREFIX + state.strategyId, JSON.stringify(state));
  } catch { /* ignore */ }
}

export function resetPaperState(strategyId: string): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(STATE_KEY_PREFIX + strategyId);
  } catch { /* ignore */ }
}
