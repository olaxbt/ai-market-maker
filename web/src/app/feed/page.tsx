"use client";

export default function Page() {
  if (typeof window !== "undefined") {
    const qs = new URLSearchParams(window.location.search);
    const provider = (qs.get("provider") ?? "").trim();
    const next = new URLSearchParams({ focus: "signals" });
    if (provider) next.set("provider", provider);
    window.location.replace(`/leaderboard?${next.toString()}`);
  }

  return (
    <div className="flex min-h-screen items-center justify-center text-xs text-[var(--nexus-muted)]">
      Opening signals…
    </div>
  );
}
