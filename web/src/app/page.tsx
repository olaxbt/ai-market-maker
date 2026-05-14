"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    // Hosted entrypoint: show results first.
    router.replace("/leaderboard");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-xs text-[var(--nexus-muted)]">
      Opening Leaderboard…
    </div>
  );
}

