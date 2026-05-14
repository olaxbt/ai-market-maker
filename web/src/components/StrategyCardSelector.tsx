"use client";

import { useMemo } from "react";

// ── Types ──

export type StrategyCategory = "trend" | "mean_reversion" | "balanced";

export interface StrategyOption {
  id: string;
  title: string;
  description: string;
  category: string;
  reasoning_preview: string;
  defaults: {
    n_bars: number;
    interval_sec: number;
    max_steps: number;
    seed: number;
    fee_bps: number;
    initial_cash: number;
  };
}

const CATEGORY_META: Record<string, { icon: string; brief: string; emoji: string }> = {
  trend: {
    icon: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
    brief: "Follows directional moves with confirmation filters",
    emoji: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  },
  mean_reversion: {
    icon: "M13 22L3 10h9l-1-8 10 12h-9l1 8z",
    brief: "Buys dips, sells rips; works in range-bound markets",
    emoji: "M13 22L3 10h9l-1-8 10 12h-9l1 8z",
  },
  balanced: {
    icon: "M12 2v10l5 5m-5-5L7 17m5-5L7 7m5 5l5-5",
    brief: "Adaptively blends trend and reversion by regime",
    emoji: "M12 2v10l5 5m-5-5L7 17m5-5L7 7m5 5l5-5",
  },
};

// ── Helpers ──

function catIcon(category: string, size: number = 16): string {
  const meta = CATEGORY_META[category];
  if (!meta) return "";
  return meta.icon;
}

function catLabel(cat: StrategyCategory | string): string {
  const labels: Record<string, string> = {
    trend: "Trend-following",
    mean_reversion: "Mean reversion",
    balanced: "Balanced / Adaptive",
  };
  return labels[cat] ?? cat;
}

function strDefault(key: string, val: number): string {
  if (key === "interval_sec") {
    if (val >= 86400) return `${val / 86400}d`;
    if (val >= 3600) return `${val / 3600}h`;
    if (val >= 60) return `${val / 60}min`;
    return `${val}s`;
  }
  if (key === "initial_cash") return `$${val.toLocaleString()}`;
  return String(val);
}

// ── Main component ──

export function StrategyCardSelector({
  strategies,
  selectedId,
  onSelect,
  disabled,
}: {
  strategies: StrategyOption[];
  selectedId: string;
  onSelect: (id: string) => void;
  disabled: boolean;
}) {
  if (!strategies.length) return null;

  return (
    <div className="space-y-2">
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {strategies.map((s) => {
          const isActive = s.id === selectedId;
          const isDisabled = disabled && !isActive;
          return (
            <button
              key={s.id}
              type="button"
              disabled={isDisabled}
              onClick={() => onSelect(s.id)}
              className={`
                relative flex flex-col rounded-xl border p-3 text-left transition-all
                ${
                  isActive
                    ? "border-[rgba(0,212,170,0.5)] bg-[rgba(0,212,170,0.07)] shadow-[0_0_16px_rgba(0,212,170,0.08)] ring-1 ring-[rgba(0,212,170,0.2)]"
                    : "border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/25 hover:border-[rgba(138,149,166,0.3)] hover:bg-[var(--nexus-surface)]/35"
                }
                ${isDisabled ? "opacity-30 cursor-not-allowed" : "cursor-pointer"}
              `}
            >
              {/* Category badge */}
              <span
                className={`mb-1.5 inline-flex w-fit rounded-full px-2 py-0.5 font-mono text-[8px] uppercase tracking-wider ${
                  isActive
                    ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.85)]"
                    : "bg-[rgba(138,149,166,0.08)] text-[var(--nexus-muted)]"
                }`}
              >
                {catLabel(s.category)}
              </span>

              {/* Title */}
              <span
                className={`text-[11px] font-semibold ${
                  isActive ? "text-white" : "text-[rgba(226,232,240,0.75)]"
                }`}
              >
                {s.title}
              </span>

              {/* Description */}
              <p className="mt-1 text-[10px] leading-snug text-[var(--nexus-muted)] line-clamp-2">
                {s.description}
              </p>

              {/* Defaults snapshot */}
              <div className="mt-2 flex flex-wrap gap-1">
                {Object.entries(s.defaults)
                  .filter(([k]) => !["seed", "fee_bps"].includes(k))
                  .slice(0, 3)
                  .map(([k, v]) => (
                    <span
                      key={k}
                      className="rounded border border-[rgba(138,149,166,0.12)] bg-[rgba(138,149,166,0.04)] px-1.5 py-0.5 font-mono text-[8px] tabular-nums text-[rgba(138,149,166,0.7)]"
                    >
                      {k === "n_bars"
                        ? `${v} bars`
                        : k === "max_steps"
                          ? `${v} steps`
                          : strDefault(k, v)}
                    </span>
                  ))}
              </div>

              {/* Active indicator */}
              {isActive && (
                <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[rgba(0,212,170,0.7)]" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Config Receipt ──

export function ConfigReceiptPanel({
  strategy,
  resolvedParams,
}: {
  strategy: StrategyOption;
  resolvedParams: {
    n_bars: number;
    interval_amount: string;
    interval_unit: string;
    interval_sec: number;
    max_steps: number;
    fee_bps: number;
    initial_cash: number;
    ticker: string;
    data_source: string;
    window_mode: string;
    since_iso: string;
    until_iso: string;
  };
}) {
  const paramEntries = useMemo(() => {
    const p = resolvedParams;
    return [
      { key: "ticker", val: p.ticker },
      { key: "data source", val: p.data_source },
      { key: "preset", val: strategy.title },
      { key: "candles", val: String(p.n_bars) },
      { key: "bar interval", val: `${p.interval_amount} ${p.interval_unit}` },
      { key: "max steps", val: String(p.max_steps) },
      { key: "fee (bps)", val: String(p.fee_bps) },
      { key: "initial cash", val: `$${p.initial_cash.toLocaleString()}` },
      { key: "window", val: p.window_mode === "range" ? `${p.since_iso} → ${p.until_iso}` : "Latest N" },
    ];
  }, [strategy, resolvedParams]);

  return (
    <div className="rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.35)] p-3">
      <div className="mb-2 flex items-center gap-2">
        <span className="font-mono text-[9px] uppercase tracking-widest text-[var(--nexus-muted)]">
          Config receipt
        </span>
        <div className="h-px flex-1 bg-[rgba(138,149,166,0.08)]" />
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 sm:grid-cols-3">
        {paramEntries.map(({ key, val }) => (
          <div key={key} className="flex flex-col">
            <span className="font-mono text-[8px] uppercase tracking-wider text-[var(--nexus-muted)]">
              {key}
            </span>
            <span className="font-mono text-[10px] tabular-nums text-[rgba(226,232,240,0.8)]">
              {val}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Reasoning Preview ──

export function ReasoningPreviewCard({
  reasoning,
  title,
}: {
  reasoning: string;
  title: string;
}) {
  const lines = reasoning
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);

  return (
    <details open className="group rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.35)] transition-all">
      <summary className="flex cursor-pointer items-center gap-2 p-3 transition hover:bg-[rgba(255,255,255,0.02)]">
        <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-[rgba(99,102,241,0.3)] bg-[rgba(99,102,241,0.08)] text-[8px] text-[rgba(99,102,241,0.8)] font-mono">
          C
        </div>
        <span className="flex-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
          Chain of thought · {title}
        </span>
        <svg
          className="h-3 w-3 text-[var(--nexus-muted)] transition group-open:rotate-180"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>
      <div className="border-t border-[rgba(138,149,166,0.08)] px-3 pb-3 pt-2">
        <ol className="space-y-1">
          {lines.map((line, i) => {
            // Strip leading numbering for rendering
            const stepMatch = line.match(/^(\d+)\.\s*(.*)/);
            if (stepMatch) {
              const [, num, text] = stepMatch;
              return (
                <li key={i} className="flex gap-2 text-[10px] leading-relaxed text-[rgba(226,232,240,0.7)]">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded bg-[rgba(99,102,241,0.1)] font-mono text-[8px] text-[rgba(99,102,241,0.7)]">
                    {num}
                  </span>
                  <span>{text}</span>
                </li>
              );
            }
            return (
              <li key={i} className="text-[10px] leading-relaxed text-[rgba(226,232,240,0.7)] pl-6">
                {line}
              </li>
            );
          })}
        </ol>
      </div>
    </details>
  );
}
