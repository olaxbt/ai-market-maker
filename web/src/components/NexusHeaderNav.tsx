"use client";

import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";

export type HeaderNavMode = "observe" | "nexus";

function SecondaryTab({
  href,
  label,
  active,
  title,
  onClick,
  emphasize,
}: {
  href: string;
  label: string;
  active: boolean;
  title?: string;
  onClick?: () => void;
  emphasize?: boolean;
}) {
  const emphasis = emphasize
    ? "rounded-lg border border-[rgba(0,212,170,0.38)] bg-[rgba(0,212,170,0.10)] shadow-[0_0_14px_rgba(0,212,170,0.07)]"
    : "";
  const cls = `${emphasis} relative px-3 py-2 text-[11px] transition ${
    active ? "text-[var(--nexus-text)]" : "text-[var(--nexus-muted)] hover:text-[var(--nexus-text)]"
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
    <div className="w-full rounded-2xl border border-[var(--nexus-card-stroke)] bg-[var(--nexus-surface)]/95 px-2 py-1">
      {label ? (
        <div className="px-2 pt-1 text-[9px] uppercase tracking-[0.22em] text-[var(--nexus-muted)]">
          {label}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-1 px-1 pb-1">{children}</div>
    </div>
  );
}

function Divider() {
  return <span className="mx-0.5 h-6 w-px shrink-0 bg-[rgba(138,149,166,0.18)]" aria-hidden />;
}

/**
 * Single Nexus navigation strip (console, leaderboard header, section pages).
 * Leaderboard is reached via direct URL/bookmarks — not duplicated here.
 */
export function NexusHeaderNav() {
  const pathname = usePathname() || "/";
  const searchParams = useSearchParams();
  const consoleView = (searchParams.get("view") ?? "").trim();

  const isConsoleTopology = pathname === "/console" && !consoleView;
  const isConsoleAgents = pathname === "/console" && consoleView === "grid";
  const isConsoleResearch = pathname === "/console" && consoleView === "research";
  const isConsoleMonitor = pathname === "/console" && consoleView === "monitor";
  const isNexusApprovals = pathname === "/inbox";
  const isNexusPaper = pathname === "/paper";
  const isNexusPublishing = pathname === "/platform/providers";
  const isConsoleFutu = pathname === "/console" && consoleView === "futu";

  return (
    <div className="min-w-0 flex-1">
      <SecondaryBar label="Nexus">
        <SecondaryTab href="/console" label="Topology" active={isConsoleTopology} title="Live topology + event stream" />
        <SecondaryTab href="/console?view=grid" label="Agents" active={isConsoleAgents} title="Agent grid + detail panel" />
        <SecondaryTab
          href="/console?view=research"
          label="Research"
          active={isConsoleResearch}
          title="Backtest + supervisor (shared run context)"
        />
        <SecondaryTab
          href="/console?view=monitor"
          label="Monitor"
          active={isConsoleMonitor}
          title="Balances, positions, and last decisions"
        />

        <Divider />

        <SecondaryTab
          href="/console?view=futu"
          label="Futu"
          active={isConsoleFutu}
          title="Futu OpenD — HK/US stocks, quotes, paper flow (console tab)"
          emphasize
        />
        <SecondaryTab href="/inbox" label="Approvals" active={isNexusApprovals} title="Your approvals queue" />
        <SecondaryTab href="/paper" label="Paper" active={isNexusPaper} title="Paper portfolio + fills" />
        <SecondaryTab href="/platform/providers" label="Provider keys" active={isNexusPublishing} title="Publisher keys" />

        <Divider />

        <SecondaryTab href="/get-started" label="Get Started" active={pathname === "/get-started"} title="Clone + run locally" />
        <SecondaryTab href="/control" label="Control" active={pathname === "/control"} title="Control Center (ops)" />
        <SecondaryTab href="/tools" label="Tools" active={pathname === "/tools"} title="Browse platform tools" />
      </SecondaryBar>
    </div>
  );
}
