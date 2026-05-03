/**
 * Local strategy persistence using localStorage.
 *
 * Saves/loads StrategyConfig and BacktestRunResult summaries so the user
 * can return to their strategies across sessions without a backend.
 *
 * Flattenable JSON payload for "saved strategy" cards in My Strategies panel.
 */

import type { BacktestMetrics } from "@/types/backtest";

export interface StrategyConfig {
  ticker: string;
  interval_sec: number;
  n_bars: number;
  fee_bps: number;
  initial_cash: number;
  agent_ids: string[];
  description: string;
}

export interface SavedStrategy {
  id: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  config: StrategyConfig;
  summary?: {
    total_return_pct: number;
    sharpe: number;
    max_drawdown: number;
    win_rate: number;
    profit_factor: number;
    total_trades: number;
  } | null;
}

const STORAGE_KEY = "aimm_studio_strategies";

function loadAll(): SavedStrategy[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveAll(strategies: SavedStrategy[]): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(strategies));
  } catch {
    // localStorage full or unavailable — silently fail
  }
}

export function listStrategies(): SavedStrategy[] {
  return loadAll();
}

export function getStrategy(id: string): SavedStrategy | undefined {
  return loadAll().find((s) => s.id === id);
}

export function saveStrategy(
  name: string,
  config: StrategyConfig,
  metrics?: BacktestMetrics | null,
): SavedStrategy {
  const all = loadAll();
  const now = new Date().toISOString();

  // Compute a digest of the config to detect duplicates
  const configKey = `${config.ticker}:${config.agent_ids.sort().join(",")}:${config.interval_sec}:${config.n_bars}`;

  // If the exact same config exists, update it instead of creating a duplicate
  const existing = all.find(
    (s) =>
      `${s.config.ticker}:${s.config.agent_ids.sort().join(",")}:${s.config.interval_sec}:${s.config.n_bars}` ===
      configKey,
  );

  const summary = metrics
    ? {
        total_return_pct: metrics.sharpe > 0
          ? ((metrics.final_equity / metrics.initial_cash) - 1) * 100
          : 0,
        sharpe: metrics.sharpe,
        max_drawdown: metrics.max_drawdown,
        win_rate: metrics.win_rate,
        profit_factor: metrics.profit_factor ?? 0,
        total_trades: metrics.steps,
      }
    : null;

  if (existing) {
    existing.name = name;
    existing.updatedAt = now;
    existing.summary = summary ?? existing.summary;
    saveAll(all);
    return existing;
  }

  const strategy: SavedStrategy = {
    id: `strat_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`,
    name,
    createdAt: now,
    updatedAt: now,
    config,
    summary,
  };

  all.unshift(strategy);
  // Keep max 50 strategies
  if (all.length > 50) all.length = 50;
  saveAll(all);
  return strategy;
}

export function deleteStrategy(id: string): void {
  const all = loadAll().filter((s) => s.id !== id);
  saveAll(all);
}

export function renameStrategy(id: string, name: string): void {
  const all = loadAll();
  const found = all.find((s) => s.id === id);
  if (found) {
    found.name = name;
    found.updatedAt = new Date().toISOString();
    saveAll(all);
  }
}
