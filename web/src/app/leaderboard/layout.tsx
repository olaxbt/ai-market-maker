import { Suspense } from "react";

export default function LeaderboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[var(--nexus-bg)] nexus-bg" aria-hidden />}>
      {children}
    </Suspense>
  );
}
