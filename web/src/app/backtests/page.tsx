"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Bookmark: open the console on Research (backtest + supervisor). */
export default function BacktestsRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/console?view=research");
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--nexus-bg)] font-mono text-xs text-[var(--nexus-muted)]">
      Opening saved runs (Research)…
    </div>
  );
}
