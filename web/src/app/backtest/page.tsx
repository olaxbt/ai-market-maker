"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Backtests always run inside Research (backtest + supervisor). Keep /backtest as a deep link. */
export default function BacktestRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/console?view=research");
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--nexus-bg)] font-mono text-xs text-[var(--nexus-muted)]">
      Opening console (Research)…
    </div>
  );
}
