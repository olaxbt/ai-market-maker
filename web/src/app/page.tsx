"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    router.replace("/console?view=flow");
  }, [router]);

  return (
    <div className="flex min-h-screen items-center justify-center text-xs text-[var(--nexus-muted)]">
      Opening Live desk…
    </div>
  );
}
