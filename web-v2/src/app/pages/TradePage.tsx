import type * as React from "react";
import { Link } from "react-router";
import { ArrowRight, FlaskConical, LayoutDashboard, LineChart, ShieldCheck, TerminalSquare } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

function Tile({
  title,
  body,
  to,
  cta,
  icon,
}: {
  title: string;
  body: string;
  to: string;
  cta: string;
  icon: React.ReactNode;
}) {
  return (
    <Card className="group hover:bg-muted/20 transition-colors">
      <CardHeader className="gap-2">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-border bg-muted/20 text-foreground/80">
              {icon}
            </span>
            <CardTitle className="text-[14px]">{title}</CardTitle>
          </div>
        </div>
        <CardDescription className="text-[12px]">{body}</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <Link
          to={to}
          className="inline-flex items-center gap-2 rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[12px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)]"
        >
          {cta} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
        </Link>
      </CardContent>
    </Card>
  );
}

export default function TradePage() {
  return (
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">AI Trade</div>
            <h1 className="mt-1 text-[18px] font-semibold">Run • Monitor • Review • Read signals</h1>
            <p className="mt-1 text-[12px] text-muted-foreground">
              A single hub for operating the system. Start with Account, build strategy in Studio, operate via Console,
              and compare results in Leaderboard.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to="/account"
              className="rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[12px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)]"
            >
              Start here → Account
            </Link>
            <Link to="/studio" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
              Open Studio
            </Link>
            <Link
              to="/leaderboard"
              className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
            >
              Open Leaderboard
            </Link>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Tile
            title="Account checklist"
            body="Connect / verify your environment and credentials before operating."
            to="/account"
            cta="Open Account"
            icon={<ShieldCheck className="h-4 w-4" />}
          />
          <Tile
            title="Strategy Studio"
            body="Build, backtest, and iterate strategies in a chat-first workspace."
            to="/studio"
            cta="Open Studio"
            icon={<LayoutDashboard className="h-4 w-4" />}
          />
          <Tile
            title="Run backtest"
            body="Presets, publish to leaderboard, and run receipts live on Backtests."
            to="/backtests"
            cta="Open Backtests"
            icon={<FlaskConical className="h-4 w-4" />}
          />
          <Tile
            title="Console: live ops"
            body="Watch decisions, balances and system events."
            to="/console"
            cta="Open Console"
            icon={<TerminalSquare className="h-4 w-4" />}
          />
          <Tile
            title="Results"
            body="Compare local runs and published providers."
            to="/leaderboard"
            cta="Open Results"
            icon={<LineChart className="h-4 w-4" />}
          />
          <Tile
            title="Signals"
            body="Read provider notes and live ops updates."
            to="/leaderboard?focus=signals"
            cta="Open Signals"
            icon={<LineChart className="h-4 w-4" />}
          />
        </div>
      </div>
    </div>
  );
}

