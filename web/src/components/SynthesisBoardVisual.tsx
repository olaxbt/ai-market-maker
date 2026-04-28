"use client";

import { motion } from "framer-motion";
import { Scale, TrendingDown, TrendingUp } from "lucide-react";
import type { SynthesisBoardPayload } from "@/types/nexus-payload";

interface SynthesisBoardVisualProps {
  board: SynthesisBoardPayload;
  reduceMotion?: boolean;
}

export function SynthesisBoardVisual({ board, reduceMotion = false }: SynthesisBoardVisualProps) {
  const bull = board.bull_case;
  const bear = board.bear_case;
  const scores = board.scores ?? {};
  const consensus = board.consensus ?? {};
  const bullW =
    typeof scores.bull_weight === "number" && Number.isFinite(scores.bull_weight)
      ? Math.min(1, Math.max(0, scores.bull_weight))
      : 0.5;

  const bullLines = Array.isArray(bull?.lines) ? bull.lines : [];
  const bearLines = Array.isArray(bear?.lines) ? bear.lines : [];

  const inner = (
    <div className="rounded-lg border border-[color:var(--nexus-card-stroke)] bg-gradient-to-b from-[var(--nexus-bg)]/80 to-[var(--nexus-panel)]/40 overflow-hidden">
      <div className="px-3 py-2.5 border-b border-[var(--nexus-rule-soft)] bg-[var(--nexus-panel)]/60 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <Scale size={15} className="shrink-0 text-[var(--nexus-glow)]" />
          <div className="min-w-0">
            <div className="text-[10px] font-bold uppercase tracking-widest text-[var(--nexus-glow)]">
              Evidence board
            </div>
            <div className="text-[10px] text-[var(--nexus-muted)] truncate">
              {board.headline ?? "Desk thesis before chair synthesis"}
            </div>
          </div>
        </div>
        {board.ticker ? (
          <span className="shrink-0 font-mono text-[10px] text-[var(--nexus-muted)] tabular-nums">
            {board.ticker}
          </span>
        ) : null}
      </div>

      <div className="px-3 py-2 border-b border-[var(--nexus-rule-soft)]/80">
        <div className="flex justify-between text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] mb-1">
          <span>Score blend</span>
          <span className="tabular-nums">
            {scores.bull_score ?? "—"} bull · {scores.bear_score ?? "—"} bear
            {scores.sentiment_score != null
              ? ` · sent ${Number(scores.sentiment_score).toFixed(0)}`
              : ""}
          </span>
        </div>
        <div className="h-2 rounded-full bg-[var(--nexus-bg)] border border-[var(--nexus-rule-soft)] overflow-hidden flex">
          <div
            className="h-full bg-gradient-to-r from-emerald-600/90 to-emerald-400/70 transition-[width] duration-500 ease-out"
            style={{ width: `${bullW * 100}%` }}
            title="Constructive weight"
          />
          <div
            className="flex-1 h-full bg-gradient-to-l from-rose-700/85 to-rose-500/55"
            title="Defensive weight"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 divide-y sm:divide-y-0 sm:divide-x divide-[var(--nexus-rule-soft)]">
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-emerald-400/95">
            <TrendingUp size={14} className="shrink-0" />
            <span className="text-[10px] font-bold uppercase tracking-widest">
              {bull?.label ?? "Constructive"}
            </span>
            {typeof bull?.signal_count === "number" ? (
              <span className="text-[9px] text-[var(--nexus-muted)] tabular-nums">
                ({bull.signal_count} raw)
              </span>
            ) : null}
          </div>
          <ul className="space-y-1.5 list-none">
            {bullLines.map((line, i) => (
              <li
                key={i}
                className="font-mono text-[11px] leading-snug text-[var(--nexus-text)]/90 pl-2 border-l-2 border-emerald-500/35"
              >
                {line}
              </li>
            ))}
          </ul>
        </div>
        <div className="p-3 space-y-2">
          <div className="flex items-center gap-1.5 text-rose-400/95">
            <TrendingDown size={14} className="shrink-0" />
            <span className="text-[10px] font-bold uppercase tracking-widest">
              {bear?.label ?? "Defensive"}
            </span>
            {typeof bear?.signal_count === "number" ? (
              <span className="text-[9px] text-[var(--nexus-muted)] tabular-nums">
                ({bear.signal_count} raw)
              </span>
            ) : null}
          </div>
          <ul className="space-y-1.5 list-none">
            {bearLines.map((line, i) => (
              <li
                key={i}
                className="font-mono text-[11px] leading-snug text-[var(--nexus-text)]/90 pl-2 border-l-2 border-rose-500/35"
              >
                {line}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {(consensus.summary || consensus.block_aggressive_long) && (
        <div className="px-3 py-2.5 border-t border-[var(--nexus-rule-soft)] bg-[var(--nexus-bg)]/25">
          <div className="text-[9px] font-semibold uppercase tracking-widest text-[var(--nexus-muted)] mb-1">
            Tier-0 consensus
          </div>
          {consensus.summary ? (
            <p className="font-mono text-[11px] leading-relaxed text-[var(--nexus-text)]/85">
              {consensus.summary}
            </p>
          ) : null}
          {consensus.block_aggressive_long ? (
            <p className="mt-1 font-mono text-[10px] text-amber-400/90">
              Aggressive long blocked by desk consensus.
            </p>
          ) : null}
        </div>
      )}
    </div>
  );

  if (reduceMotion) {
    return inner;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      {inner}
    </motion.div>
  );
}
