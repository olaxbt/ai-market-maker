"use client";

import { useCallback, useEffect, useState } from "react";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";

export type DeskBacktestJob = {
  run_id?: string;
  status?: string;
  step?: number;
  total_steps?: number;
  source?: string;
};

export type DeskStatus = {
  mode?: "idle" | "live" | "research" | "dual" | string;
  owner?: string;
  paper_running?: boolean;
  paper_run_id?: string | null;
  paper_ticker?: string | null;
  paper_interval_sec?: number | null;
  paper_started_at?: number | null;
  paper_phase?: string | null;
  paper_scan_iteration?: number | null;
  paper_last_scan_started_at?: number | null;
  paper_last_scan_finished_at?: number | null;
  paper_next_scan_at?: number | null;
  paper_updated_at?: number | null;
  active_backtest_id?: string | null;
  active_backtests?: DeskBacktestJob[];
  latest_paper_id?: string | null;
  latest_backtest_id?: string | null;
  can_start_paper?: boolean;
  can_start_backtest?: boolean;
  message?: string;
};

export function useDeskOwnership(pollMs = 4000) {
  const [desk, setDesk] = useState<DeskStatus | null>(null);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch(`${getFlowApiOrigin()}/engine/desk`, { cache: "no-store" });
      if (!res.ok) return;
      setDesk((await res.json()) as DeskStatus);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), pollMs);
    return () => window.clearInterval(id);
  }, [pollMs, refresh]);

  return { desk, refresh };
}
