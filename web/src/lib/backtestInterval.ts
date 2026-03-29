/** Human-friendly bar spacing; API still uses `interval_sec`. */

export type BarIntervalUnit = "sec" | "min" | "hr" | "day";

const MULT: Record<BarIntervalUnit, number> = {
  sec: 1,
  min: 60,
  hr: 3600,
  day: 86400,
};

/** Pick the largest unit that divides evenly so presets like 300 → 5 min not 300 sec. */
export function intervalSecToAmountUnit(sec: number): { amount: string; unit: BarIntervalUnit } {
  const s = Math.max(1, Math.floor(Number(sec) || 1));
  if (s % MULT.day === 0) return { amount: String(s / MULT.day), unit: "day" };
  if (s % MULT.hr === 0) return { amount: String(s / MULT.hr), unit: "hr" };
  if (s % MULT.min === 0) return { amount: String(s / MULT.min), unit: "min" };
  return { amount: String(s), unit: "sec" };
}

export function amountUnitToIntervalSec(amount: number, unit: BarIntervalUnit): number {
  const m = MULT[unit] ?? 1;
  const v = Number.isFinite(amount) ? amount : 1;
  return Math.max(1, Math.round(v * m));
}

export const BAR_INTERVAL_UNIT_LABEL: Record<BarIntervalUnit, string> = {
  sec: "Seconds",
  min: "Minutes",
  hr: "Hours",
  day: "Days",
};

const INTERVAL_WORD: Record<BarIntervalUnit, [string, string]> = {
  sec: ["second", "seconds"],
  min: ["minute", "minutes"],
  hr: ["hour", "hours"],
  day: ["day", "days"],
};

/** Short label for run summaries (e.g. "1 day", "5 minutes"). */
export function formatIntervalHuman(sec: number): string {
  const s = Math.max(1, Math.floor(Number(sec) || 1));
  const { amount, unit } = intervalSecToAmountUnit(s);
  const n = Number(amount);
  const [one, many] = INTERVAL_WORD[unit];
  const word = n === 1 ? one : many;
  return `${n} ${word}`;
}
