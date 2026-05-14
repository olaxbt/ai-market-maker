import { useEffect, useMemo, useState } from "react";
import type * as React from "react";
import { Link, useLocation, useNavigate } from "react-router";
import { HelpCircle, Rocket, Wrench } from "lucide-react";

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "../components/ui/accordion";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

type GuideSection = "get-started" | "tools" | "what-is-aimm";

function asSection(v: string | null): GuideSection | null {
  if (v === "get-started") return "get-started";
  if (v === "tools") return "tools";
  if (v === "what-is-aimm") return "what-is-aimm";
  return null;
}

export default function GuidesPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const repoUrl = "https://github.com/olaxbt/ai-market-maker";

  const section = useMemo(() => {
    const qs = new URLSearchParams(location.search);
    return asSection(qs.get("section"));
  }, [location.search]);

  const [open, setOpen] = useState<GuideSection>(section ?? "get-started");

  useEffect(() => {
    setOpen(section ?? "get-started");
  }, [section]);

  useEffect(() => {
    if (!section) return;
    const el = document.getElementById(`guide-${section}`);
    if (!el) return;
    queueMicrotask(() => el.scrollIntoView({ block: "start" }));
  }, [section]);

  return (
    <div className="flex-1 min-h-0 overflow-auto">
      <div className="px-4 pt-6 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div className="min-w-0">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Guides</p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">Quick references</h1>
              <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
                The hosted site is best for browsing results. To run the full AIMM workflow (backtests, paper, agents), you’ll
                run the stack locally.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => navigate("/guides?section=get-started")}
                className={[
                  "rounded-lg border px-3 py-2 text-sm transition-colors",
                  open === "get-started" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/70",
                ].join(" ")}
              >
                Get started
              </button>
              <button
                type="button"
                onClick={() => navigate("/guides?section=tools")}
                className={[
                  "rounded-lg border px-3 py-2 text-sm transition-colors",
                  open === "tools" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/70",
                ].join(" ")}
              >
                Tools
              </button>
              <button
                type="button"
                onClick={() => navigate("/guides?section=what-is-aimm")}
                className={[
                  "rounded-lg border px-3 py-2 text-sm transition-colors",
                  open === "what-is-aimm" ? "border-border bg-muted/60 text-foreground" : "border-border bg-card hover:bg-muted/70",
                ].join(" ")}
              >
                What is AIMM?
              </button>
              <a
                href={repoUrl}
                target="_blank"
                rel="noreferrer noopener"
                className="rounded-lg border border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-sm font-semibold text-[rgba(0,212,170,0.95)] hover:bg-[rgba(0,212,170,0.14)]"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
      </div>

      <div className="px-4 pb-10 pt-4 sm:px-6">
        <div className="mx-auto w-full max-w-6xl">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Guide sections</CardTitle>
              <CardDescription>Local setup, where to click in the product, and what AIMM refers to.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4 grid gap-3 lg:grid-cols-2">
                <div className="rounded-xl border border-border bg-muted/10 p-3">
                  <div className="text-sm font-medium">If you’re just browsing</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    Use the <b className="text-foreground">Leaderboard</b> and provider pages. No login required.
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/leaderboard">
                      Open Leaderboard
                    </Link>
                  </div>
                </div>
                <div className="rounded-xl border border-border bg-muted/10 p-3">
                  <div className="text-sm font-medium">If you want to run AIMM</div>
                  <div className="mt-1 text-sm text-muted-foreground">
                    Start locally: backtests generate runs; Console shows traces; Control tunes runtime settings.
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => navigate("/guides?section=get-started")}
                      className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70"
                    >
                      Open Get started
                    </button>
                    <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/console">
                      Open Console
                    </Link>
                  </div>
                </div>
              </div>
              <Accordion
                type="single"
                collapsible
                value={open}
                onValueChange={(v) => {
                  const next = asSection(v);
                  if (!next) return;
                  setOpen(next);
                  navigate(`/guides?section=${encodeURIComponent(next)}`, { replace: true });
                }}
              >
                <AccordionItem value="get-started" id="guide-get-started">
                  <AccordionTrigger>
                    <span className="inline-flex items-center gap-2">
                      <Rocket className="h-4 w-4 opacity-80" />
                      Get started (local)
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-3">
                    <div className="text-sm text-muted-foreground">
                      Run backtests + the full agent workflow locally. The hosted UI is mainly for browsing published results.
                    </div>
                    <div className="grid gap-3 lg:grid-cols-3">
                      <StepCard title="1) Clone">
                        <pre className="overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-[11px]">
                          {`git clone https://github.com/olaxbt/ai-market-maker\ncd ai-market-maker`}
                        </pre>
                      </StepCard>
                      <StepCard title="2) Configure">
                        <pre className="overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-[11px]">
                          {`cp .env.example .env\n# then edit .env`}
                        </pre>
                      </StepCard>
                      <StepCard title="3) Run">
                        <pre className="overflow-auto rounded-lg border border-border bg-muted/20 p-3 text-[11px]">
                          {`docker compose -f docker-compose.prod.yml up -d --build\ndocker compose -f docker-compose.prod.yml run --rm api alembic upgrade head`}
                        </pre>
                      </StepCard>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Then: run a first backtest, and open Console to watch traces.
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/backtests">
                        Backtests (run)
                      </Link>
                      <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/console">
                        Console (trace)
                      </Link>
                      <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/control">
                        Control Center (diagnostics)
                      </Link>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="tools" id="guide-tools">
                  <AccordionTrigger>
                    <span className="inline-flex items-center gap-2">
                      <Wrench className="h-4 w-4 opacity-80" />
                      Tools (where things live)
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-3">
                    <div className="text-sm text-muted-foreground">
                      Day-to-day ops happen in the Console. Diagnostics and tuning live in Control Center. Backtests are separate.
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      <StepCard title="Console">
                        <div className="text-sm text-muted-foreground">
                          Use <b className="text-foreground">Topology / Agents / Research / Monitor</b> to inspect live runs and traces.
                        </div>
                        <div className="mt-3">
                          <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/console">
                            Open Console
                          </Link>
                        </div>
                      </StepCard>
                      <StepCard title="Control Center">
                        <div className="text-sm text-muted-foreground">
                          Health checks, API capability flags, and harness memory limits.
                        </div>
                        <div className="mt-3">
                          <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/control">
                            Open Control Center
                          </Link>
                        </div>
                      </StepCard>
                      <StepCard title="Backtests">
                        <div className="text-sm text-muted-foreground">
                          Presets, run workflow, receipts, and saved run list.
                        </div>
                        <div className="mt-3">
                          <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/backtests">
                            Open Backtests
                          </Link>
                        </div>
                      </StepCard>
                    </div>
                    <div className="text-sm text-muted-foreground">
                      Optional: browse the Flow tool surface under <code className="text-xs">/tools</code>.
                    </div>
                    <div>
                      <Link className="rounded-lg border border-border bg-card px-3 py-2 text-sm hover:bg-muted/70" to="/tools">
                        Open tool browser
                      </Link>
                    </div>
                  </AccordionContent>
                </AccordionItem>

                <AccordionItem value="what-is-aimm" id="guide-what-is-aimm">
                  <AccordionTrigger>
                    <span className="inline-flex items-center gap-2">
                      <HelpCircle className="h-4 w-4 opacity-80" />
                      What is AIMM?
                    </span>
                  </AccordionTrigger>
                  <AccordionContent className="space-y-3">
                    <div className="text-sm text-muted-foreground">
                      AIMM is an agentic trading workflow with governance and traceability: decisions produce artifacts, traces, and publishable results.
                    </div>
                    <div className="grid gap-3 lg:grid-cols-2">
                      <StepCard title="How it works (high level)">
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div>1) Market data → desk agents produce signals/theses</div>
                          <div>2) Portfolio desk proposes positions</div>
                          <div>3) Risk Guard can veto any execution</div>
                          <div>4) Runs produce trace + artifacts (equity/trades/events)</div>
                          <div>5) You publish results/signals to the leaderboard</div>
                        </div>
                      </StepCard>
                      <StepCard title="What you do locally">
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <div>- Run backtests (reproducible artifacts)</div>
                          <div>- Run paper/live simulation</div>
                          <div>- Generate signals/results</div>
                          <div>- Publish to the hosted leaderboard</div>
                        </div>
                      </StepCard>
                    </div>
                  </AccordionContent>
                </AccordionItem>
              </Accordion>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StepCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-muted/10 p-3">
      <div className="text-sm font-medium">{title}</div>
      <div className="mt-2">{children}</div>
    </div>
  );
}

