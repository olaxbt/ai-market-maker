"use client";

import Link from "next/link";

export function LoginRequiredPanel({
  title = "Login required",
  body = "This page requires a platform session. Sign in to continue.",
  cta = "Sign in",
}: {
  title?: string;
  body?: string;
  cta?: string;
}) {
  return (
    <section className="rounded-2xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.06)] p-4">
      <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(0,212,170,0.9)]">
        {title}
      </div>
      <p className="mt-2 text-[11px] text-[rgba(226,232,240,0.88)]">{body}</p>
      <div className="mt-3 flex items-center gap-2">
        <Link
          href="/platform/login"
          className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
        >
          {cta}
        </Link>
        <Link
          href="/leaderboard"
          className="rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.35)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.88)] hover:border-[rgba(0,212,170,0.32)] hover:text-white"
        >
          Back to Leaderboard
        </Link>
      </div>
    </section>
  );
}

