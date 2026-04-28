"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import type { HeaderNavMode } from "@/components/NexusHeaderNav";

function Tab({
  href,
  label,
  active,
  title,
}: {
  href: string;
  label: string;
  active: boolean;
  title?: string;
}) {
  return (
    <Link
      href={href}
      title={title}
      className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
        active ? "is-active" : ""
      }`}
    >
      {label}
    </Link>
  );
}

function isPathActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  if (href === "/leadpage") return pathname === "/leadpage" || pathname.startsWith("/leadpage/");
  if (href === "/console") return pathname === "/console";
  if (href.startsWith("/console?")) return pathname === "/console";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NexusSubtabs({ active }: { active: HeaderNavMode }) {
  const pathname = usePathname() || "/";
  const [authed, setAuthed] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/platform/providers", { cache: "no-store" });
        if (!cancelled) setAuthed(res.status !== 401);
      } catch {
        if (!cancelled) setAuthed(null);
      }
    }
    void check();
    return () => {
      cancelled = true;
    };
  }, []);

  const tabs = useMemo(() => {
    if (active === "observe") {
      return [
        { href: "/leadpage", label: "Results", title: "Leaderboard results" },
        { href: "/feed", label: "Signals", title: "Provider signals feed" },
      ];
    }
    if (active === "nexus") {
      return [
        { href: "/console", label: "Topology", title: "Live topology + event stream" },
        { href: "/console?view=grid", label: "Agents", title: "Agent grid + detail panel" },
        { href: "/console?view=research", label: "Research", title: "Backtest + supervisor together" },
        { href: "/console?view=monitor", label: "Monitor", title: "Balances, positions, and last decisions" },
      ];
    }
    // Fallback (shouldn't happen).
    return authed != null ? [] : [];
  }, [active, authed]);

  return (
    <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
      {tabs.map((t) => (
        <Tab key={t.href} href={t.href} label={t.label} title={t.title} active={isPathActive(pathname, t.href)} />
      ))}
    </div>
  );
}

