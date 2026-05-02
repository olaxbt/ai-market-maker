"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { Orbit, Trophy } from "lucide-react";

export type HeaderNavMode = "observe" | "nexus";

export type NexusViewMode = "nexus" | "grid" | "backtest" | "supervisor" | "monitor" | "research";

function SecondaryTab({
  href,
  label,
  active,
  title,
  onClick,
}: {
  href: string;
  label: string;
  active: boolean;
  title?: string;
  onClick?: () => void;
}) {
  const cls = `relative px-3 py-2 text-[11px] transition ${
    active ? "text-[rgba(226,232,240,0.98)]" : "text-[rgba(226,232,240,0.78)] hover:text-white"
  } ${
    active
      ? "after:content-[''] after:absolute after:left-2 after:right-2 after:-bottom-[1px] after:h-[3px] after:rounded-full after:bg-[rgba(0,212,170,0.75)]"
      : ""
  }`;

  if (onClick) {
    return (
      <button type="button" onClick={onClick} title={title} className={cls}>
        {label}
      </button>
    );
  }

  return (
    <Link href={href} title={title} className={cls}>
      {label}
    </Link>
  );
}

function SecondaryBar({
  children,
  label,
}: {
  children: React.ReactNode;
  label?: string;
}) {
  return (
    <div className="w-full rounded-2xl border border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.22)] px-2 py-1">
      {label ? (
        <div className="px-2 pt-1 text-[9px] uppercase tracking-[0.22em] text-[rgba(138,149,166,0.85)]">
          {label}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-1 px-1 pb-1">{children}</div>
    </div>
  );
}

function PrimaryTab({
  href,
  active,
  title,
  icon,
  label,
}: {
  href: string;
  active: boolean;
  title: string;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <Link
      href={href}
      title={title}
      className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-[11px] font-semibold tracking-wide transition ${
        active
          ? "border-[rgba(0,212,170,0.35)] bg-[rgba(0,212,170,0.14)] text-[rgba(226,232,240,0.98)]"
          : "border-[rgba(138,149,166,0.16)] bg-[rgba(6,8,11,0.28)] text-[rgba(226,232,240,0.86)] hover:border-[rgba(0,212,170,0.28)] hover:text-white"
      }`}
    >
      {icon}
      {label}
    </Link>
  );
}

export function NexusHeaderNav({
  active,
  variant,
  viewMode,
  onViewModeChange,
}: {
  active: HeaderNavMode;
  variant: "section" | "console";
  viewMode?: NexusViewMode;
  onViewModeChange?: (mode: NexusViewMode) => void;
  viewModeTitle?: string;
}) {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const leaderboardFocus = searchParams.get("focus") === "signals" ? "signals" : "overview";
  const consoleView = (searchParams.get("view") ?? "").trim();

  const isConsoleTopology = pathname === "/console" && !consoleView;
  const isConsoleAgents = pathname === "/console" && consoleView === "grid";
  const isConsoleResearch = pathname === "/console" && consoleView === "research";
  const isConsoleMonitor = pathname === "/console" && consoleView === "monitor";
  const isNexusApprovals = pathname === "/inbox";
  const isNexusPaper = pathname === "/paper";
  const isNexusPublishing = pathname === "/platform/providers";

  return (
    <div className="w-full">
      <div className="flex flex-wrap items-center gap-2">
        <PrimaryTab
          href="/leadpage"
          active={active === "observe"}
          title="Leaderboard: results + signals"
          icon={<Trophy className="h-4 w-4 opacity-85" />}
          label="Leaderboard"
        />

        <PrimaryTab
          href="/console"
          active={active === "nexus"}
          title="Nexus: topology, agents, research, monitor"
          icon={<Orbit className="h-4 w-4 opacity-85" />}
          label="Nexus"
        />
      </div>

      <div className="mt-2 w-full">
        {active === "observe" ? (
          <SecondaryBar label="Leaderboard">
            <SecondaryTab
              href="/leadpage"
              label="Overview"
              active={(pathname === "/leadpage" || pathname.startsWith("/leadpage/")) && leaderboardFocus !== "signals"}
              title="Leaderboard results"
            />
            <SecondaryTab
              href="/leadpage?focus=signals"
              label="Signals"
              active={pathname === "/leadpage" && leaderboardFocus === "signals"}
              title="Signals feed (inside Leaderboard)"
            />
          </SecondaryBar>
        ) : active === "nexus" ? (
          <SecondaryBar label="Nexus">
            {variant === "console" ? (
              <>
                <SecondaryTab
                  href="/console"
                  label="Topology"
                  active={viewMode === "nexus"}
                  onClick={() => onViewModeChange?.("nexus")}
                />
                <SecondaryTab
                  href="/console?view=grid"
                  label="Agents"
                  active={viewMode === "grid"}
                  onClick={() => onViewModeChange?.("grid")}
                />
                <SecondaryTab
                  href="/console?view=research"
                  label="Research"
                  active={viewMode === "research"}
                  onClick={() => onViewModeChange?.("research")}
                />
                <SecondaryTab
                  href="/console?view=monitor"
                  label="Monitor"
                  active={viewMode === "monitor"}
                  onClick={() => onViewModeChange?.("monitor")}
                />
              </>
            ) : (
              <>
                <SecondaryTab href="/console" label="Topology" active={isConsoleTopology} />
                <SecondaryTab href="/console?view=grid" label="Agents" active={isConsoleAgents} />
                <SecondaryTab href="/console?view=research" label="Research" active={isConsoleResearch} />
                <SecondaryTab href="/console?view=monitor" label="Monitor" active={isConsoleMonitor} />

                <span className="mx-1 h-6 w-px bg-[rgba(138,149,166,0.18)]" />
                <SecondaryTab href="/inbox" label="Approvals" active={isNexusApprovals} title="Your approvals queue" />
                <SecondaryTab href="/paper" label="Paper" active={isNexusPaper} title="Paper portfolio + fills" />
                <SecondaryTab
                  href="/platform/providers"
                  label="Provider keys"
                  active={isNexusPublishing}
                  title="Publisher keys"
                />
              </>
            )}
          </SecondaryBar>
        ) : null}
      </div>
    </div>
  );
}

