/**
 * Agent trace row (thought chain, proposal, veto). See `schema/agent_trace.json` and
 * `src/schemas/agent_trace.py`.
 */
export interface TraceActor {
  id: string;
  role: string;
  persona_ref?: string;
}

export interface TraceContext {
  pair?: string;
  signal?: string;
  confidence?: number;
  [key: string]: unknown;
}

export interface ThoughtStep {
  step: number;
  label: string;
  detail: string;
}

export interface TraceProposal {
  action: string;
  params: Record<string, unknown>;
}

export interface TraceVetoStatus {
  checked_by: string;
  status: "APPROVED" | "REJECTED" | "MODIFIED";
  reason?: string;
}

export interface AgentTrace {
  trace_id: string;
  timestamp: string;
  actor: TraceActor;
  context: TraceContext;
  thought_process: ThoughtStep[];
  proposal?: TraceProposal;
  veto_status?: TraceVetoStatus;
  run_id?: string;
}
