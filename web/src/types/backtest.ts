/** Flow API: POST /backtests/preset and GET /backtests/{id}/summary */

export type BacktestMetrics = {
  sharpe: number;
  sortino?: number;
  max_drawdown: number;
  win_rate: number;
  profit_factor?: number | null;
  periods_per_year?: number;
  final_equity: number;
  initial_cash: number;
  steps: number;
  interval_sec: number;
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
  interval_sec?: number;
  count: number;
  max_points: number;
  downsampled: boolean;
  bars: OhlcvBar[];
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
};

export type TradesResponse = {
  run_id: string;
  total: number;
  returned: number;
  truncated: boolean;
  trades: TradeRow[];
};

export type SummaryPayload = {
  run_id: string;
  ticker: string;
  steps: number;
  interval_sec: number;
  trade_count: number;
  metrics: BacktestMetrics;
  paths?: Record<string, string>;
};
