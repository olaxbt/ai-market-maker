"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

/** Backtest lives on the main console (Backtest tab). Keep /backtest as a deep link. */
export default function BacktestRedirectPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/?view=backtest");
  }, [router]);
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--nexus-bg)] font-mono text-xs text-[var(--nexus-muted)]">
      Opening Nexus console (Backtest tab)…
    </div>
  );
}
