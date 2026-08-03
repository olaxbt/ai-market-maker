/** Flow API backtest types */

export type BacktestMetrics = {
  sharpe: number;
  sortino?: number;
  /** Fraction 0–1 (legacy) or missing when max_drawdown_pct is used. */
  max_drawdown?: number;
  /** Percent units (engine summary.json). */
  max_drawdown_pct?: number;
  /** Fraction 0–1 (legacy). */
  win_rate?: number;
  /** Percent units (engine summary.json). */
  win_rate_pct?: number;
  total_return_pct?: number;
  total_pnl_usd?: number;
  total_commission?: number;
  total_trades?: number;
  profit_factor?: number | null;
  periods_per_year?: number;
  final_equity?: number;
  initial_cash?: number;
  steps?: number;
  interval_sec?: number;
};

export type SavedRunListItem = {
  run_id: string;
  ticker?: string | null;
  start_iso?: string | null;
  end_iso?: string | null;
  interval_sec?: number | null;
  initial_cash?: number | null;
  final_equity?: number | null;
  total_return_pct?: number | null;
  total_pnl_usd?: number | null;
  sharpe?: number | null;
  total_trades?: number | null;
  eval_bars?: number | null;
  equity_points?: number | null;
  has_charts?: boolean;
  sort_ts?: number;
};

export type BacktestEvaluation = {
  initial_cash: number;
  final_equity: number;
  total_return_pct: number;
  trade_count: number;
  trades_preview: Record<string, unknown>[];
  note?: string;
};

export type BacktestRunResult = {
  run_id: string;
  steps: number;
  trade_count: number;
  metrics: BacktestMetrics;
  evaluation?: BacktestEvaluation;
  strategy?: { preset_id: string; title: string; description?: string };
  paths?: { summary: string; trades: string; equity: string; events?: string };
  capped?: boolean;
  server_max_steps?: number;
};

export type EquityPoint = {
  step: number;
  ts_ms: number;
  close?: number;
  equity: number;
  vetoed?: boolean;
};

export type EquitySeriesResponse = {
  run_id: string;
  count: number;
  max_points: number;
  downsampled: boolean;
  points: EquityPoint[];
};

export type OhlcvBar = {
  step: number;
  ts_ms: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

export type BarsResponse = {
  run_id: string;
  ticker?: string;
  benchmark_symbol?: string;
  interval_sec?: number;
  fill_model?: string;
  count: number;
  max_points: number;
  downsampled: boolean;
  bars: OhlcvBar[];
  /** Buy&hold equity path aligned to returned bars (same units as strategy equity). */
  benchmark_equity?: number[];
};

export type TradeRow = {
  step: number;
  ts_ms?: number;
  side: string;
  qty: number;
  price: number;
  cash?: number;
  qty_base?: number;
  vetoed?: boolean;
  fee_bps?: number;
  symbol?: string;
  pnl?: number;
  pnl_usd?: number;
  exit_reason?: string;
  holding_bars?: number;
};

export type TradesResponse = {
  run_id: string;
  total: number;
  returned: number;
  truncated: boolean;
  trades: TradeRow[];
};

export type BacktestBenchmark = {
  benchmark_symbol?: string;
  benchmark_asset_return_pct?: number;
  benchmark_buy_hold_equity_return_pct?: number;
  excess_return_vs_buy_hold_equity_pct?: number;
  benchmark_first_close?: number;
  benchmark_last_close?: number;
};

export type SummaryPayload = {
  run_id: string;
  ticker?: string;
  symbols?: string[];
  steps?: number;
  interval_sec?: number;
  bar_interval_sec_inferred?: number;
  trade_count?: number;
  initial_cash?: number;
  final_equity?: number;
  start_iso?: string;
  end_iso?: string;
  eval_bars?: number;
  total_bars?: number;
  leverage?: number;
  instrument?: string;
  timeframe?: string;
  metrics: BacktestMetrics;
  benchmark?: BacktestBenchmark;
  quality_report?: Record<string, unknown>;
  paths?: Record<string, string>;
};
