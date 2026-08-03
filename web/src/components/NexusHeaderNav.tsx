"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { parseConsoleView } from "@/lib/consoleView";

export type HeaderNavMode = "observe" | "nexus";

function SecondaryTab({
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
  const cls = `relative shrink-0 whitespace-nowrap px-3 py-2 text-[11px] transition ${
    active ? "text-[var(--nexus-text)]" : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
  } ${
    active
      ? "after:content-[''] after:absolute after:left-2 after:right-2 after:-bottom-[1px] after:h-[3px] after:rounded-full after:bg-[rgba(0,212,170,0.75)]"
      : ""
  }`;

  return (
    <Link href={href} title={title} className={cls}>
      {label}
    </Link>
  );
}

function SecondaryBar({ children }: { children: React.ReactNode }) {
  return (
    <div className="w-full rounded-2xl border border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/95 px-2 py-1">
      <div className="flex flex-nowrap items-center gap-1.5 overflow-x-auto overflow-y-hidden overscroll-x-contain px-1 pb-1 [-ms-overflow-style:none] [scrollbar-width:thin] lg:flex-wrap lg:overflow-x-visible [&::-webkit-scrollbar]:h-1 [&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-[rgba(138,149,166,0.25)]">
        {children}
      </div>
    </div>
  );
}

export function NexusHeaderNav() {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const viewMode = parseConsoleView(searchParams.get("view"), searchParams.get("run"));
  const onConsole = pathname === "/console" || pathname === "/";

  const isLiveDesk = onConsole && viewMode === "nexus";
  const isAgents = onConsole && viewMode === "grid";
  const isResearch = onConsole && viewMode === "research";
  const isPortfolio = onConsole && viewMode === "portfolio";

  return (
    <div className="min-w-0 flex-1">
      <SecondaryBar>
        <SecondaryTab
          href="/console?view=flow"
          label="Live desk"
          active={isLiveDesk}
          title="Live trading desk + agent map and thoughts"
        />
        <SecondaryTab
          href="/console?view=grid"
          label="Agents"
          active={isAgents}
          title="Inspect individual agents and prompts"
        />
        <SecondaryTab
          href="/console?view=research"
          label="Research"
          active={isResearch}
          title="Backtests + Supervisor in one console"
        />
        <SecondaryTab
          href="/console?view=portfolio"
          label="Portfolio"
          active={isPortfolio}
          title="Live/paper book only (not backtests)"
        />
      </SecondaryBar>
    </div>
  );
}
