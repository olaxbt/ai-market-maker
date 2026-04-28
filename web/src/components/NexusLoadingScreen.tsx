"use client";

export function NexusLoadingScreen({ label = "Loading" }: { label?: string }) {
  return (
    <div className="fixed inset-0 z-50 flex min-h-screen items-center justify-center bg-[var(--nexus-bg)]">
      <div className="flex flex-col items-center gap-3">
        <div className="h-10 w-10 rounded-full border border-[rgba(0,212,170,0.35)] border-t-transparent shadow-[0_0_24px_rgba(0,212,170,0.10)] animate-spin" />
        <div className="text-[10px] tracking-[0.22em] uppercase text-[var(--nexus-muted)]">
          {label}
        </div>
      </div>
    </div>
  );
}
