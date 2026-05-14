"use client";

import { Suspense } from "react";
import { FeedPage } from "@/features/feed/FeedPage";

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-xs text-[var(--nexus-muted)]">
          Loading signals…
        </div>
      }
    >
      <FeedPage />
    </Suspense>
  );
}
