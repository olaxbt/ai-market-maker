import type { NexusViewMode } from "@/components/NexusConsoleHeader";

export function isBacktestRunId(run: string | null | undefined): boolean {
  const id = (run || "").trim();
  return /^(bt[-_]|perp[-_])/i.test(id);
}

export function parseConsoleView(
  rawView: string | null | undefined,
  run: string | null | undefined = null,
): NexusViewMode {
  const v = (rawView ?? "").trim();
  if (v === "backtest" || v === "supervisor" || v === "research") return "research";
  if (v === "futu") return "futu";
  if (v === "grid") return "grid";
  if (v === "monitor" || v === "portfolio") return "portfolio";
  if (v === "flow" || v === "topology" || v === "nexus" || v === "live") return "nexus";
  if (!v && isBacktestRunId(run)) return "research";
  return "nexus";
}

export function researchConsoleHref(run?: string | null): string {
  const id = (run || "").trim();
  if (!id) return "/console?view=research";
  return `/console?view=research&run=${encodeURIComponent(id)}`;
}
