export type PortfolioManagerSnapshot = {
  run_id: string;
  steps?: number | null;
  trade_count?: number | null;
  llm_arbitrator?: boolean | null;
  returns?: Record<string, unknown>;
  fees?: Record<string, unknown>;
  trading?: Record<string, unknown>;
  intent?: Record<string, unknown>;
  paths?: Record<string, unknown> | null;
};

export type PortfolioManagerSnapshotResponse = {
  snapshot: PortfolioManagerSnapshot;
  llm_summary?: {
    brief?: string[];
    detail?: string;
    risks?: string[];
    next_actions?: string[];
  };
};

export type PortfolioManagerAskResponse = {
  run_id: string;
  question: string;
  answer: string;
  model?: string | null;
};

