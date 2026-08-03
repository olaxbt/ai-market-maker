"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useDeskOwnership } from "@/hooks/useDeskOwnership";
import { researchConsoleHref } from "@/lib/consoleView";

type Props = {
  followingResearchId?: string | null;
  onFollowResearch?: (runId: string) => void;
  onStopFollowResearch?: () => void;
};

export function DualLaneStatus({
  followingResearchId = null,
  onFollowResearch,
  onStopFollowResearch,
}: Props) {
  const { desk } = useDeskOwnership(2500);
  const [copied, setCopied] = useState(false);

  const researchId = (desk?.active_backtest_id || "").trim();
  const researchOn = Boolean(researchId);
  const following = Boolean(followingResearchId && followingResearchId === researchId);
  const show = researchOn || Boolean(followingResearchId);

  const copyId = useCallback(async () => {
    const id = researchId || followingResearchId;
    if (!id) return;
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch {
      // ignore
    }
  }, [followingResearchId, researchId]);

  if (!desk || !show) return null;

  const bt = desk.active_backtests?.[0];
  const step =
    bt && typeof bt.step === "number" && typeof bt.total_steps === "number" && bt.total_steps > 0
      ? `${bt.step}/${bt.total_steps}`
      : null;
  const id = researchId || (followingResearchId || "").trim();

  return (
    <div className="flex shrink-0 flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-[rgba(59,130,246,0.35)] bg-[rgba(59,130,246,0.08)] px-4 py-2">
      <span className="font-mono text-[9px] uppercase tracking-wider text-[rgba(147,197,253,0.95)]">
        Research
      </span>
      <span className="font-mono text-[9px] uppercase tracking-wider text-[rgba(147,197,253,0.95)]">
        {researchOn ? "running" : "idle"}
      </span>
      {step ? (
        <span className="font-mono text-[10px] tabular-nums text-[var(--nexus-muted)]">{step}</span>
      ) : null}
      {id ? (
        <button
          type="button"
          onClick={() => void copyId()}
          title="Click to copy backtest id"
          className="min-w-0 max-w-full truncate font-mono text-[10px] text-[var(--nexus-text)] hover:text-[rgba(147,197,253,0.95)]"
        >
          {id}
          <span className="ml-1.5 text-[9px] uppercase tracking-wider text-[var(--nexus-muted)]">
            {copied ? "copied" : "copy"}
          </span>
        </button>
      ) : null}
      {following ? (
        <span className="font-mono text-[9px] uppercase tracking-wider text-[rgba(147,197,253,0.95)]">
          following stream
        </span>
      ) : null}

      <div className="ml-auto flex flex-wrap items-center gap-2">
        {researchOn ? (
          following ? (
            <button
              type="button"
              onClick={() => onStopFollowResearch?.()}
              className="rounded-md border border-[color:var(--nexus-card-stroke)] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
            >
              Stop follow
            </button>
          ) : (
            <button
              type="button"
              onClick={() => onFollowResearch?.(researchId)}
              className="rounded-md border border-[rgba(59,130,246,0.45)] bg-[rgba(59,130,246,0.12)] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[rgba(147,197,253,0.95)] hover:bg-[rgba(59,130,246,0.2)]"
            >
              Follow stream
            </button>
          )
        ) : null}
        {id ? (
          <Link
            href={researchConsoleHref(id)}
            className="rounded-md border border-[color:var(--nexus-card-stroke)] px-2.5 py-1 font-mono text-[9px] uppercase tracking-wider text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
          >
            Open Research
          </Link>
        ) : null}
      </div>
    </div>
  );
}
