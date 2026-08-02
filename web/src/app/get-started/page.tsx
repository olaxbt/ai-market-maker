"use client";

import Link from "next/link";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

export default function GetStartedPage() {
  return (
    <div className="nexus-bg min-h-screen">
      <NexusSectionHeader
        title="GET STARTED"
        subtitle="Clone → configure → docker compose → Research."
        active="nexus"
      />
      <div className="mx-auto w-full max-w-4xl px-6 py-10">
        <div className="rounded-2xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.20)] p-6">
          <div className="text-[11px] uppercase tracking-[0.18em] text-[rgba(138,149,166,0.55)]">
            Local showcase
          </div>
          <h1 className="mt-1 text-[20px] font-semibold text-[rgba(226,232,240,0.95)]">
            Run agentic backtests on your machine
          </h1>
          <p className="mt-2 text-[12px] leading-relaxed text-[rgba(138,149,166,0.75)]">
            No sign-in required for Research. Put an LLM key in <code>.env</code>, start Docker, then open Research
            and run a preset against Binance (crypto) or Yahoo Finance (equities). Futu OpenD is optional.
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
              href="/console?view=research"
              className="rounded-xl border border-[rgba(138,149,166,0.16)] bg-[rgba(138,149,166,0.06)] px-4 py-2 text-[11px] text-[rgba(226,232,240,0.9)] hover:bg-[rgba(138,149,166,0.10)]"
            >
              Open Research
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
# Required for agentic backtests:
#   OPENAI_API_KEY=...
# Optional: OPENAI_BASE_URL / OPENAI_MODEL (DeepSeek-compatible works)
# DATABASE_URL + AIMM_AUTH_SECRET already default for local Docker`}
            </pre>
          </Section>

          <Section title="3) Run the stack">
            <pre className="mt-2 overflow-auto rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.35)] p-4 text-[11px] text-[rgba(226,232,240,0.9)]">
{`docker compose up --build -d
# Migrations run automatically (service: migrate).
# Futu OpenD (only if you use the Futu tab):
#   docker compose --profile with-futu up --build -d`}
            </pre>
            <div className="mt-2 text-[11px] text-[rgba(138,149,166,0.75)]">
              Then open{" "}
              <Link className="text-[rgba(0,212,170,0.92)] hover:underline" href="/console?view=research">
                Research
              </Link>
              → pick a strategy → <b>Run backtest</b> (sticky at the top of the form). LLM keys come from{" "}
              <code>.env</code> at container runtime.
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
