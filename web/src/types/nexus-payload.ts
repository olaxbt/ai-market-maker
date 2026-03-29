/** Dashboard payload: run metadata, graph topology, traces (optional parent_id for provenance). */

export interface Metadata {
  run_id: string;
  ticker: string;
  status: string;
  version?: string;
  pid?: number;
  kpis: {
    pnl?: string;
    win_rate?: number;
    sharpe?: number;
    latency?: string;
    [key: string]: unknown;
  };
}

export type NodeStatus = "COMPLETED" | "ACTIVE" | "PENDING";

export interface TopologyNode {
  id: string;
  actor: string;
  label: string;
  status: NodeStatus;
  summary?: string;
  avatar_url?: string;
  pos?: { x: number; y: number };
}

export interface TopologyEdge {
  from: string;
  to: string;
}

export interface Topology {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
}

export interface TraceContent {
  thought_process?: Array<{ step: number; label: string; detail: string }>;
  signal?: string;
  confidence?: number;
  formula?: string | { name?: string; latex?: string; computed?: string };
  proposal?: { action: string; params: Record<string, unknown> };
  /** Optional non-proposal decision payload (e.g. tool result). */
  decision?: unknown;
  /** Optional extra metadata from reasoning events (e.g. tool args). */
  extra?: Record<string, unknown>;
  veto_status?: { checked_by?: string; status: string; reason?: string };
  context?: { pair?: string; signal?: string; confidence?: number; [key: string]: unknown };
}

export interface NexusTrace {
  trace_id: string;
  node_id: string;
  parent_id?: string;
  timestamp: string;
  actor: { id: string; role: string; persona?: string };
  content: TraceContent;
  /** 0-based bar index when emitted from backtest (aligns with `message_log`). */
  bar_step?: number;
  bar_time_utc?: string;
}

/** Per-agent prompt and model fields for the settings UI. */
export interface AgentPromptSettings {
  node_id: string;
  actor_id: string;
  system_prompt: string;
  task_prompt: string;
  cot_enabled: boolean;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  tools?: string[];
  stop_sequences?: string[];
  response_format?: string;
}

/** Flat timeline for stream UIs; `seq` is monotonic; `trace_id` may reference `traces[]`. */
export interface MessageLogEntry {
  seq: number;
  ts: string;
  node_id: string;
  actor_id: string;
  kind: "status" | "thought" | "tool" | "handoff" | "error";
  message: string;
  trace_id?: string;
  /** 0-based bar index when emitted from backtest (see `bar_time_utc`). */
  bar_step?: number;
  bar_time_utc?: string;
}

export interface NexusPayload {
  metadata: Metadata;
  topology: Topology;
  traces: NexusTrace[];
  agent_prompts?: AgentPromptSettings[];
  message_log?: MessageLogEntry[];
}
