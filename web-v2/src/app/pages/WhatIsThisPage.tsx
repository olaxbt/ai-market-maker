import type * as React from "react";
import { Link } from "react-router";

const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

export default function WhatIsThisPage() {
  return (
    <div className="flex-1 min-h-0 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-5xl">
        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            Overview
          </div>
          <h1 className="mt-1 text-[20px] font-semibold">
            What is AI Market Maker?
          </h1>
          <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
            AI Market Maker is an agentic trading system (hedge-fund style
            workflow) with a strict governance layer (“Risk Guard”) and full
            traceability. This hosted site is mainly for evaluating results and
            published signals; execution happens when you run the stack locally.
          </p>

          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to="/studio"
              className="rounded-xl border border-border bg-muted/30 px-3 py-2 text-[11px] hover:bg-muted/70"
            >
              Open Studio
            </Link>
            <Link
              to="/get-started"
              className="rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[11px] text-[rgba(0,212,170,0.9)] hover:bg-[rgba(0,212,170,0.12)]"
            >
              Get Started (local)
            </Link>
            <Link
              to="/tools"
              className="rounded-xl border border-[rgba(99,102,241,0.16)] bg-[rgba(99,102,241,0.06)] px-3 py-2 text-[11px] text-[rgba(99,102,241,0.9)] hover:bg-[rgba(99,102,241,0.10)]"
            >
              Tools
            </Link>
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="rounded-xl border border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground hover:text-foreground"
            >
              GitHub repo
            </a>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Card title="How it works (high level)">
            <div className="space-y-2 text-[12px]">
              <div>1) Market data → desk agents produce signals/theses</div>
              <div>2) Portfolio desk proposes positions</div>
              <div>3) Risk Guard can veto any execution</div>
              <div>4) Runs produce trace + artifacts (equity/trades/events)</div>
              <div>5) You publish results/signals to the hosted leaderboard</div>
            </div>
          </Card>
          <Card title="What you can do here (hosted)">
            <div className="space-y-2 text-[12px]">
              <div>- Browse leaderboard results + provider profiles</div>
              <div>- Read published signals</div>
              <div>- Inspect the platform tool surface</div>
              <div>- Learn how to run locally (Get Started)</div>
            </div>
          </Card>
          <Card title="What you do locally (after cloning)">
            <div className="space-y-2 text-[12px]">
              <div>- Run backtests (reproducible artifacts)</div>
              <div>- Run paper/live simulation</div>
              <div>- Generate signals/results</div>
              <div>- Publish to the hosted leaderboard</div>
            </div>
          </Card>
          <Card title="OpenClaw usage (quick path)">
            <div className="space-y-2 text-[12px]">
              <div>
                This repo ships an OpenClaw skill under <code>openclaw/</code>.
              </div>
              <div className="rounded-xl border border-border bg-muted/30 p-3 text-[11px]">
                <pre className="whitespace-pre-wrap">{`# from inside the cloned repo
claw skill install ./openclaw

# run the OpenClaw runner
python3 openclaw/scripts/claw_runner.py --backtest`}</pre>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="text-[12px] font-semibold">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

