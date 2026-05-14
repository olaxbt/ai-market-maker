import { NavLink, useLocation } from "react-router";
import React from "react";
import {
  MessageSquare,
  LineChart,
  Trophy,
  Activity,
  X,
  SlidersHorizontal,
  UserRound,
  ScrollText,
  LogIn,
  ShieldCheck,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect, useState } from "react";
import PlatformLoginPage from "../pages/PlatformLoginPage";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "./ui/dialog";

interface NavigationProps {
  isOpen: boolean;
  onToggle: () => void;
}

type NavItem = {
  to: string;
  icon: LucideIcon;
  label: string;
};

type GroupLink = { to: string; icon: LucideIcon; label: string };
type NavGroup = { id: string; title: string; links: GroupLink[] };

const GROUPS: NavGroup[] = [
  {
    id: "platform",
    title: "Platform",
    links: [
      { to: "/workspace", icon: UserRound, label: "Workspace" },
      { to: "/control", icon: SlidersHorizontal, label: "Control Center" },
    ],
  },
  {
    id: "guides",
    title: "Guides",
    links: [
      { to: "/guides", icon: ScrollText, label: "Guides" },
    ],
  },
];

export default function Navigation({ isOpen, onToggle }: NavigationProps) {
  const location = useLocation();
  const [sessionState, setSessionState] = useState<"unknown" | "required" | "present">("unknown");
  const [loginOpen, setLoginOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        const res = await fetch("/api/platform/providers", { cache: "no-store" as any });
        if (cancelled) return;
        if (res.status === 401) setSessionState("required");
        else if (res.ok) setSessionState("present");
        else setSessionState("unknown");
      } catch {
        if (!cancelled) setSessionState("unknown");
      }
    }
    void check();
    const t = window.setInterval(check, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  useEffect(() => {
    function onOpenLogin() {
      setLoginOpen(true);
    }
    window.addEventListener("aimm:open-login", onOpenLogin as any);
    return () => window.removeEventListener("aimm:open-login", onOpenLogin as any);
  }, []);

  async function refreshSessionOnce() {
    try {
      const res = await fetch("/api/platform/providers", { cache: "no-store" as any });
      if (res.status === 401) setSessionState("required");
      else if (res.ok) setSessionState("present");
      else setSessionState("unknown");
    } catch {
      setSessionState("unknown");
    }
  }

  const navItems: NavItem[] = [
    { to: "/studio", icon: MessageSquare, label: "Studio Chat" },
    { to: "/console", icon: Activity, label: "Nexus Console" },
    { to: "/leaderboard", icon: Trophy, label: "Leaderboard" },
    { to: "/backtests", icon: LineChart, label: "Backtests" },
  ];

  const baseItemClass = "w-full flex items-center gap-3 rounded-lg transition-colors";
  const baseActive = "bg-sidebar-accent text-sidebar-foreground";
  const baseIdle = "text-sidebar-foreground hover:bg-sidebar-accent/80";

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onToggle}
        />
      )}

      {/* Navigation Sidebar */}
      <aside
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          w-64 bg-sidebar border-r border-sidebar-border
          transform transition-transform duration-200 ease-in-out
          ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
          flex flex-col
        `}
      >
        {/* Header */}
        <div className="p-4 border-b border-sidebar-border">
          <div className="flex items-center justify-between mb-1">
            <h2 className="text-sidebar-foreground">AI Market Maker</h2>
            <button
              onClick={onToggle}
              className="lg:hidden p-2 rounded-lg hover:bg-sidebar-accent/80 transition-colors"
            >
              <X className="w-4 h-4 text-sidebar-foreground" />
            </button>
          </div>
          <p className="text-xs text-muted-foreground">Agentic Hedge Fund OS</p>
        </div>

        {/* Navigation Items */}
        <nav className="flex-1 p-3 space-y-3">
          <div>
            <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              App
            </div>
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={() => {
                  if (window.innerWidth < 1024) onToggle();
                }}
                className={({ isActive }) =>
                  [
                    baseItemClass,
                    "px-3 py-2.5 text-sm",
                    isActive ? baseActive : baseIdle,
                  ].join(" ")
                }
              >
                <Icon className="h-4 w-4 shrink-0 opacity-90" />
                <span className="truncate">{item.label}</span>
              </NavLink>
            );
          })}
          </div>

          <div className="pt-3 border-t border-sidebar-border space-y-3">
            {GROUPS.map((g) => (
              <div key={g.id}>
                <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {g.title}
                </div>
                <div className="space-y-0.5">
                  {g.links.map((pl) => {
                    const Icon = pl.icon;
                    return (
                      <NavLink
                        key={pl.to}
                        to={pl.to}
                        onClick={() => {
                          if (window.innerWidth < 1024) onToggle();
                        }}
                        className={({ isActive }) =>
                          [
                            "w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm",
                            "transition-colors",
                            isActive ? baseActive : baseIdle,
                          ].join(" ")
                        }
                      >
                        <Icon className="h-4 w-4 shrink-0 opacity-90" />
                        <span className="truncate">{pl.label}</span>
                      </NavLink>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </nav>

        {/* Footer */}
        <div className="p-3 border-t border-sidebar-border space-y-2">
          <button
            type="button"
            className="w-full flex items-center justify-between gap-2 rounded-lg border border-sidebar-border bg-sidebar px-2.5 py-2 transition-colors hover:bg-sidebar-accent/90 hover:border-sidebar-border/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            aria-label={sessionState === "present" ? "Account (open settings)" : "Account (sign in)"}
            title={
              sessionState === "unknown"
                ? "Couldn’t verify login status (network / API). Click to sign in."
                : sessionState === "present"
                  ? "Logged in. Click to open settings."
                  : "Logged out. Click to sign in."
            }
            onClick={() => {
              if (sessionState === "present") {
                window.location.href = "/workspace?tab=settings";
                if (window.innerWidth < 1024) onToggle();
              } else {
                setLoginOpen(true);
              }
            }}
          >
            <div className="flex min-w-0 items-center gap-2">
              <span
                className={[
                  "h-2 w-2 rounded-full",
                  sessionState === "present"
                    ? "bg-emerald-500"
                    : sessionState === "required"
                      ? "bg-amber-500"
                      : "bg-muted-foreground/40",
                ].join(" ")}
                aria-hidden="true"
              />
              {sessionState === "present" ? (
                <ShieldCheck className="h-4 w-4 opacity-90" />
              ) : (
                <LogIn className="h-4 w-4 opacity-90" />
              )}
              <span className="truncate text-[12px] font-medium">
                {sessionState === "present" ? "Logged in" : "Logged out"}
              </span>
            </div>
            <UserRound className="h-4 w-4 opacity-70" />
          </button>
        </div>
      </aside>

      <Dialog open={loginOpen} onOpenChange={setLoginOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Sign in</DialogTitle>
            <DialogDescription>Use your email and password to continue.</DialogDescription>
          </DialogHeader>
          <PlatformLoginPage
            embedded
            hideEmbeddedHeader
            onAuthed={async () => {
              setLoginOpen(false);
              await refreshSessionOnce();
            }}
          />
        </DialogContent>
      </Dialog>
    </>
  );
}
