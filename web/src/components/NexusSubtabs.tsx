"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useMemo } from "react";
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
  if (href === "/feed") return pathname === "/feed";
  if (href === "/console") return pathname === "/console";
  if (href.startsWith("/console?")) return pathname === "/console";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function NexusSubtabs({ active }: { active: HeaderNavMode }) {
  const pathname = usePathname() || "/";

  const tabs = useMemo(() => {
    if (active === "observe") {
      return [{ href: "/feed", label: "Signals", title: "Provider signals feed" }];
    }
    if (active === "nexus") {
      return [
        { href: "/console", label: "Topology", title: "Live topology + event stream" },
        { href: "/console?view=grid", label: "Agents", title: "Agent grid + detail panel" },
        { href: "/console?view=research", label: "Research", title: "Backtest + supervisor together" },
        { href: "/console?view=monitor", label: "Monitor", title: "Balances, positions, and last decisions" },
        { href: "/console?view=futu", label: "Futu", title: "Futu OpenD HK/US stocks" },
      ];
    }
    return [];
  }, [active]);

  return (
    <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
      {tabs.map((t) => (
        <Tab key={t.href} href={t.href} label={t.label} title={t.title} active={isPathActive(pathname, t.href)} />
      ))}
    </div>
  );
}

