export type PaperScanPhase = "scanning" | "waiting" | string | null | undefined;

export function formatCountdown(totalSec: number): string {
  const s = Math.max(0, Math.floor(totalSec));
  const m = Math.floor(s / 60);
  const r = s % 60;
  if (m >= 60) {
    const h = Math.floor(m / 60);
    const mm = m % 60;
    return `${h}:${String(mm).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  }
  return `${m}:${String(r).padStart(2, "0")}`;
}

export function formatIntervalLabel(intervalSec: number | null | undefined): string {
  if (intervalSec == null || !Number.isFinite(intervalSec) || intervalSec <= 0) return "—";
  if (intervalSec < 60) return `${intervalSec}s`;
  if (intervalSec % 60 === 0) return `${intervalSec / 60}m`;
  return `${intervalSec}s`;
}

export function formatUptime(startedAtSec: number | null | undefined, nowSec: number): string {
  if (startedAtSec == null || !Number.isFinite(startedAtSec)) return "—";
  const elapsed = Math.max(0, nowSec - startedAtSec);
  return formatCountdown(elapsed);
}

/** Fallback: next_scan_at, else updated_at/last_scan_finished_at + interval. */
export function secondsUntilNextScan(opts: {
  nowSec: number;
  phase?: PaperScanPhase;
  nextScanAt?: number | null;
  intervalSec?: number | null;
  updatedAt?: number | null;
  lastScanFinishedAt?: number | null;
}): number | null {
  const phase = (opts.phase || "").toLowerCase();
  if (phase === "scanning") return null;

  if (typeof opts.nextScanAt === "number" && Number.isFinite(opts.nextScanAt)) {
    return Math.max(0, opts.nextScanAt - opts.nowSec);
  }

  const interval =
    typeof opts.intervalSec === "number" && opts.intervalSec > 0 ? opts.intervalSec : null;
  const anchor =
    (typeof opts.lastScanFinishedAt === "number" && Number.isFinite(opts.lastScanFinishedAt)
      ? opts.lastScanFinishedAt
      : null) ??
    (typeof opts.updatedAt === "number" && Number.isFinite(opts.updatedAt) ? opts.updatedAt : null);

  if (interval != null && anchor != null && phase !== "scanning") {
    const next = anchor + interval;
    return Math.max(0, next - opts.nowSec);
  }
  return null;
}

export function scanProgressPct(opts: {
  remainingSec: number | null;
  intervalSec?: number | null;
  phase?: PaperScanPhase;
}): number {
  const phase = (opts.phase || "").toLowerCase();
  if (phase === "scanning") return 100;
  const interval =
    typeof opts.intervalSec === "number" && opts.intervalSec > 0 ? opts.intervalSec : null;
  if (interval == null || opts.remainingSec == null) return 0;
  const done = Math.min(interval, Math.max(0, interval - opts.remainingSec));
  return Math.min(100, Math.round((done / interval) * 100));
}
