import { useEffect, useMemo, useState } from "react";
import type * as React from "react";
import { Link } from "react-router";
import { AlertTriangle, CheckCircle2, CircleDashed, KeyRound, ListChecks, LogIn, Wallet } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "../components/ui/card";

type Status = "unknown" | "ok" | "degraded";
type StepState = "todo" | "done" | "blocked";

function Pill({ status, label }: { status: Status; label: string }) {
  const cls =
    status === "ok"
      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(0,212,170,0.92)]"
      : status === "degraded"
        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
        : "border-border bg-muted/20 text-muted-foreground";
  return <span className={`rounded-lg border px-2 py-1 text-[10px] ${cls}`}>{label}</span>;
}

function StepBadge({ state }: { state: StepState }) {
  const cls =
    state === "done"
      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(0,212,170,0.92)]"
      : state === "blocked"
        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
        : "border-border bg-muted/20 text-muted-foreground";
  const Icon = state === "done" ? CheckCircle2 : state === "blocked" ? AlertTriangle : CircleDashed;
  return (
    <span className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[10px] ${cls}`}>
      <Icon className="h-3.5 w-3.5" />
      {state}
    </span>
  );
}

function StepRow({
  state,
  title,
  body,
  to,
  cta,
  icon,
}: {
  state: StepState;
  title: string;
  body: string;
  to?: string;
  cta?: string;
  icon: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-border bg-muted/10 p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-8 w-8 items-center justify-center rounded-xl border border-border bg-muted/20 text-foreground/80">
            {icon}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <StepBadge state={state} />
              <div className="text-[12px] font-semibold">{title}</div>
            </div>
            <div className="mt-1 text-[12px] text-muted-foreground">{body}</div>
          </div>
        </div>
      </div>
      {to && cta ? (
        <Link
          to={to}
          className="shrink-0 rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-3 py-2 text-[12px] font-semibold text-[rgba(0,212,170,0.92)] hover:border-[rgba(0,212,170,0.28)]"
        >
          {cta}
        </Link>
      ) : null}
    </div>
  );
}

export default function AccountPage({ embedded = false }: { embedded?: boolean }) {
  const [flowApi, setFlowApi] = useState<Status>("unknown");
  const [leaderboard, setLeaderboard] = useState<Status>("unknown");

  const [loading, setLoading] = useState(true);
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [providerCount, setProviderCount] = useState(0);
  const [followingCount, setFollowingCount] = useState(0);
  const [inboxCount, setInboxCount] = useState(0);
  const [paperHasFills, setPaperHasFills] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function check() {
      try {
        // Flow exposes `GET /health` (proxied as `/api/health`). `/api/traces` does not exist on Flow —
        // traces bootstrap matches Next.js via `/runs/latest/payload`, not `/traces`.
        const res = await fetch("/api/health", { cache: "no-store" as any });
        if (!cancelled) setFlowApi(res.ok ? "ok" : "degraded");
      } catch {
        if (!cancelled) setFlowApi("degraded");
      }
      try {
        const res = await fetch("/api/leadpage/leaderboard?limit=1", { cache: "no-store" as any });
        if (!cancelled) setLeaderboard(res.ok ? "ok" : "degraded");
      } catch {
        if (!cancelled) setLeaderboard("degraded");
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
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [provRes, folRes, inboxRes, tradesRes] = await Promise.all([
          fetch("/api/platform/providers", { cache: "no-store" as any }),
          fetch("/api/social/following", { cache: "no-store" as any }),
          fetch("/api/social/inbox?limit=1", { cache: "no-store" as any }),
          fetch("/api/paper/trades?limit=1", { cache: "no-store" as any }),
        ]);

        if (!cancelled) {
          setAuthed(!(provRes.status === 401 || folRes.status === 401 || inboxRes.status === 401 || tradesRes.status === 401));
        }

        const provJson = await provRes.json().catch(() => ({}));
        const folJson = await folRes.json().catch(() => ({}));
        const inboxJson = await inboxRes.json().catch(() => ({}));
        const tradesJson = await tradesRes.json().catch(() => ({}));

        if (!cancelled) {
          setProviderCount(Array.isArray((provJson as any)?.providers) ? (provJson as any).providers.length : 0);
          setFollowingCount(Array.isArray((folJson as any)?.providers) ? (folJson as any).providers.length : 0);
          setInboxCount(Array.isArray((inboxJson as any)?.items) ? (inboxJson as any).items.length : 0);
          setPaperHasFills(Array.isArray((tradesJson as any)?.trades) ? (tradesJson as any).trades.length > 0 : false);
        }
      } catch {
        if (!cancelled) setAuthed(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    const t = window.setInterval(load, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, []);

  const steps = useMemo(() => {
    const signedIn = Boolean(authed);
    const hasProvider = providerCount > 0;
    const followsSomeone = followingCount > 0;
    const inboxHas = inboxCount > 0;
    const hasFills = paperHasFills;

    const maybeTo = (to: string | undefined) => (embedded ? undefined : to);
    const maybeCta = (cta: string | undefined) => (embedded ? undefined : cta);

    return [
      {
        key: "login",
        state: signedIn ? ("done" as const) : ("todo" as const),
        title: "Sign in",
        body: "Create a session to access approvals, paper portfolio, and publishing keys.",
        to: maybeTo(signedIn ? undefined : "/platform/login"),
        cta: maybeCta(signedIn ? undefined : "Sign in"),
        icon: <LogIn className="h-4 w-4" />,
      },
      {
        key: "provider",
        state: !signedIn ? ("blocked" as const) : hasProvider ? ("done" as const) : ("todo" as const),
        title: "Create publisher (id + key)",
        body: "Create a publisher id and key used to publish results and signals.",
        to: maybeTo(!signedIn ? "/platform/login" : "/platform/providers"),
        cta: maybeCta(!signedIn ? "Sign in" : "Open publishing keys"),
        icon: <KeyRound className="h-4 w-4" />,
      },
      {
        key: "publish",
        state: !signedIn ? ("blocked" as const) : hasProvider ? ("todo" as const) : ("blocked" as const),
        title: "Publish a result or signal",
        body: "Use the provider key to publish a leaderboard result and/or a signal update.",
        to: maybeTo(!signedIn ? "/platform/login" : "/platform/providers"),
        cta: maybeCta(!signedIn ? "Sign in" : "Copy publish command"),
        icon: <ListChecks className="h-4 w-4" />,
      },
      {
        key: "follow",
        state: !signedIn ? ("blocked" as const) : followsSomeone ? ("done" as const) : ("todo" as const),
        title: "Follow providers",
        body: "Following routes provider updates into your inbox.",
        to: maybeTo("/leaderboard"),
        cta: maybeCta("Browse providers"),
        icon: <ListChecks className="h-4 w-4" />,
      },
      {
        key: "inbox",
        state: !signedIn ? ("blocked" as const) : inboxHas ? ("done" as const) : ("todo" as const),
        title: "Check approvals",
        body: "Approvals shows followed provider ops updates. Approved ops can execute into paper.",
        to: maybeTo("/ops?tab=queue"),
        cta: maybeCta("Open queue"),
        icon: <ListChecks className="h-4 w-4" />,
      },
      {
        key: "paper",
        state: !signedIn ? ("blocked" as const) : hasFills ? ("done" as const) : ("todo" as const),
        title: "Execute → see paper fills",
        body: "Approve an ops intent, then confirm it appears as a fill in your paper portfolio.",
        to: maybeTo("/ops?tab=paper"),
        cta: maybeCta("Open paper book"),
        icon: <Wallet className="h-4 w-4" />,
      },
    ] as const;
  }, [authed, embedded, providerCount, followingCount, inboxCount, paperHasFills]);

  const snapshotLines = useMemo(() => {
    if (loading) return null as string[] | null;
    const pub =
      providerCount === 0
        ? "No publisher profile saved yet — add keys under Provider keys."
        : `${providerCount} publisher profile${providerCount === 1 ? "" : "s"} saved.`;
    const fol =
      followingCount === 0
        ? "Not following anyone — discover traders on Leaderboard."
        : `Following ${followingCount} trader${followingCount === 1 ? "" : "s"} (updates route to your inbox).`;
    const inbox =
      inboxCount === 0
        ? "Approvals / inbox looks empty right now."
        : "There are items to review — open the queue/inbox.";
    const paper =
      paperHasFills ? "Paper shows at least one fill." : "No paper fills yet — run the queue + approvals flow.";
    return [pub, fol, inbox, paper];
  }, [loading, providerCount, followingCount, inboxCount, paperHasFills]);

  return (
    <div className={embedded ? "px-4 pb-10 sm:px-6" : "flex-1 min-h-0 overflow-auto px-6 py-10"}>
      <div className="mx-auto w-full max-w-6xl">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Workspace</div>
            <h1 className="mt-1 text-[18px] font-semibold">Workspace</h1>
            <p className="mt-1 text-[12px] text-muted-foreground">
              Live service checks plus a checklist for publisher keys, follows, approvals, and paper. Environment setup
              stays in{" "}
              <Link className="underline underline-offset-2 text-foreground/90 hover:text-foreground" to="/guides?section=get-started">
                Guides → Get started
              </Link>
              ; conversational help is under{" "}
              <Link className="underline underline-offset-2 text-foreground/90 hover:text-foreground" to="/studio">
                Studio
              </Link>
              .
            </p>
          </div>
          {embedded ? null : (
            <div className="flex flex-wrap items-center gap-2">
              <Link to="/ops?tab=queue" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
                Queue
              </Link>
              <Link to="/ops?tab=paper" className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30">
                Paper
              </Link>
              <Link
                to="/platform/providers"
                className="rounded-xl border border-border bg-card px-3 py-2 text-[12px] hover:bg-muted/30"
              >
                Provider keys
              </Link>
            </div>
          )}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <Card>
            <CardHeader className="gap-2">
              <CardTitle className="text-[14px]">System status</CardTitle>
              <CardDescription className="text-[12px]">Auto-refresh every 15s</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap items-center gap-2">
              <Pill status={flowApi} label={`Flow API: ${flowApi}`} />
              <Pill status={leaderboard} label={`Leaderboard: ${leaderboard}`} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="gap-2">
              <CardTitle className="text-[14px]">Checklist progress</CardTitle>
              <CardDescription className="text-[12px]">
                Same signals as “First run checklist” below — plain language + auto refresh every 15s.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-[12px]">
              <div className="rounded-xl border border-border bg-muted/20 px-3 py-2 text-foreground/90">
                {authed === false ? (
                  <span>
                    Sign in to see publishing keys, follows, inbox, and paper fills. Uses the same login as Publishing
                    keys.
                  </span>
                ) : authed === null ? (
                  <span className="text-muted-foreground">Couldn’t verify sign-in — check network / API.</span>
                ) : (
                  <span>Signed in — counts below reflect your workspace only.</span>
                )}
              </div>
              {loading ? (
                <div className="text-muted-foreground">Loading account snapshot…</div>
              ) : snapshotLines ? (
                <ul className="list-inside list-disc space-y-1.5 text-muted-foreground marker:text-muted-foreground/60">
                  {snapshotLines.map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              ) : null}
              <div className="text-[11px] text-muted-foreground">
                This page does not duplicate docker or repo setup — use Guides when you&apos;re provisioning the stack.
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="mt-3">
          <CardHeader>
            <CardTitle className="text-[14px]">First run checklist</CardTitle>
            <CardDescription className="text-[12px]">A guided path to a working operator loop.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {steps.map((s) => (
              <StepRow
                key={s.key}
                state={s.state}
                title={s.title}
                body={s.body}
                to={s.to}
                cta={s.cta}
                icon={s.icon}
              />
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

