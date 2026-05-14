import type * as React from "react";
import { Link } from "react-router";

const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

export default function GetStartedPage() {
  return (
    <div className="min-h-full flex-1 overflow-auto px-6 py-10">
      <div className="mx-auto w-full max-w-4xl">
        <div className="rounded-2xl border border-border bg-card p-6">
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            Get Started
          </div>
          <h1 className="mt-1 text-[20px] font-semibold">
            Clone and run AI Market Maker locally
          </h1>
          <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
            This hosted site is best for exploring the leaderboard and published
            results. To run backtests, paper trading, and the full agent workflow,
            clone the repo and run the stack locally.
          </p>

          <div className="mt-4 flex flex-wrap items-center gap-3">
            <a
              href={REPO_URL}
              target="_blank"
              rel="noreferrer noopener"
              className="rounded-xl border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] px-4 py-2 text-[11px] font-semibold text-[rgba(0,212,170,0.95)] hover:bg-[rgba(0,212,170,0.14)]"
            >
              Open GitHub repo
            </a>
            <Link
              to="/leaderboard"
              className="rounded-xl border border-border bg-muted/30 px-4 py-2 text-[11px] hover:bg-muted/70"
            >
              Back to Leaderboard
            </Link>
            <Link
              to="/tools"
              className="rounded-xl border border-[rgba(99,102,241,0.16)] bg-[rgba(99,102,241,0.06)] px-4 py-2 text-[11px] text-[rgba(99,102,241,0.9)] hover:bg-[rgba(99,102,241,0.10)]"
            >
              Browse tools
            </Link>
          </div>
        </div>

        <div className="mt-6 space-y-3">
          <Section title="1) Clone">
            <pre className="mt-2 overflow-auto rounded-xl border border-border bg-muted/30 p-4 text-[11px]">
              {`git clone ${REPO_URL}
cd ai-market-maker`}
            </pre>
          </Section>

          <Section title="2) Configure environment">
            <pre className="mt-2 overflow-auto rounded-xl border border-border bg-muted/30 p-4 text-[11px]">
              {`cp .env.example .env
# then edit .env`}
            </pre>
          </Section>

          <Section title="3) Run the stack (recommended)">
            <pre className="mt-2 overflow-auto rounded-xl border border-border bg-muted/30 p-4 text-[11px]">
              {`docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`}
            </pre>
            <div className="mt-2 text-[11px] text-muted-foreground">
              Then open <code>http://localhost:3000/leaderboard</code> and{" "}
              <code>http://localhost:3000/console</code>.
            </div>
          </Section>
        </div>
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-2xl border border-border bg-card p-6">
      <div className="text-[12px] font-semibold">{title}</div>
      {children}
    </div>
  );
}

