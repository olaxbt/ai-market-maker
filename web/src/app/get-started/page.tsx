"use client";

import Link from "next/link";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

export default function GetStartedPage() {
  return (
    <div className="nexus-bg min-h-screen">
      <NexusSectionHeader title="GET STARTED" subtitle="Clone and run locally (full capabilities)." active="studio" />
      <div className="mx-auto w-full max-w-4xl px-6 py-10">
        <div className="rounded-2xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.20)] p-6">
        <div className="text-[11px] uppercase tracking-[0.18em] text-[rgba(138,149,166,0.55)]">
          Get Started
        </div>
        <h1 className="mt-1 text-[20px] font-semibold text-[rgba(226,232,240,0.95)]">
          Clone and run AI Market Maker locally
        </h1>
        <p className="mt-2 text-[12px] leading-relaxed text-[rgba(138,149,166,0.75)]">
          This hosted site is best for exploring the leaderboard and published results. To run backtests, paper
          trading, and the full agent workflow, clone the repo and run the stack locally.
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
            href="/leaderboard"
            className="rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(138,149,166,0.06)] px-4 py-2 text-[11px] text-[rgba(226,232,240,0.9)] hover:bg-[rgba(138,149,166,0.10)]"
          >
            Back to Leaderboard
          </Link>
          <Link
            href="/tools"
            className="rounded-xl border border-[rgba(99,102,241,0.16)] bg-[rgba(99,102,241,0.06)] px-4 py-2 text-[11px] text-[rgba(99,102,241,0.9)] hover:bg-[rgba(99,102,241,0.10)]"
          >
            Browse tools
          </Link>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Section title="1) Clone">
          <pre className="mt-2 overflow-auto rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] p-4 text-[11px] text-[rgba(226,232,240,0.9)]">
{`git clone ${REPO_URL}
cd ai-market-maker`}
          </pre>
        </Section>

        <Section title="2) Configure environment">
          <pre className="mt-2 overflow-auto rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] p-4 text-[11px] text-[rgba(226,232,240,0.9)]">
{`cp .env.example .env
# then edit .env`}
          </pre>
        </Section>

        <Section title="3) Run the stack (recommended)">
          <pre className="mt-2 overflow-auto rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] p-4 text-[11px] text-[rgba(226,232,240,0.9)]">
{`docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`}
          </pre>
          <div className="mt-2 text-[11px] text-[rgba(138,149,166,0.75)]">
            Then open <code>http://localhost:3000/leaderboard</code> and <code>http://localhost:3000/console</code>.
          </div>
        </Section>
      </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.18)] p-6">
      <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.92)]">{title}</div>
      {children}
    </div>
  );
}

