"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import type { HeaderNavMode } from "@/components/NexusHeaderNav";
import { parseConsoleView } from "@/lib/consoleView";

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

export function NexusSubtabs({ active }: { active: HeaderNavMode }) {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const viewMode = parseConsoleView(searchParams.get("view"), searchParams.get("run"));

  const tabs = useMemo(() => {
    if (active === "observe") {
      return [{ href: "/feed", label: "Signals", title: "Provider signals feed", key: "feed" }];
    }
    if (active === "nexus") {
      return [
        {
          href: "/console?view=flow",
          label: "Live desk",
          title: "Live paper + agent map",
          key: "nexus",
        },
        { href: "/console?view=grid", label: "Agents", title: "Inspect agents", key: "grid" },
        {
          href: "/console?view=research",
          label: "Research",
          title: "Backtests + Supervisor",
          key: "research",
        },
        {
          href: "/console?view=portfolio",
          label: "Portfolio",
          title: "Live/paper book",
          key: "portfolio",
        },
      ];
    }
    return [];
  }, [active]);

  return (
    <div className="inline-flex rounded-xl nexus-segmented-toggle p-1">
      {tabs.map((t) => {
        const onConsole = pathname === "/console" || pathname === "/";
        const isActive =
          t.key === "feed"
            ? pathname === "/feed"
            : onConsole && viewMode === t.key;
        return (
          <Tab key={t.href} href={t.href} label={t.label} title={t.title} active={isActive} />
        );
      })}
    </div>
  );
}
