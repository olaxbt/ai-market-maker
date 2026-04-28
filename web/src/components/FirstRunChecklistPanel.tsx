"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type StepState = "todo" | "done" | "blocked";

function StepRow({
  state,
  title,
  body,
  href,
  cta,
}: {
  state: StepState;
  title: string;
  body: string;
  href?: string;
  cta?: string;
}) {
  const badge =
    state === "done"
      ? "border-[rgba(0,212,170,0.22)] bg-[rgba(0,212,170,0.08)] text-[rgba(226,232,240,0.92)]"
      : state === "blocked"
        ? "border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] text-[rgba(242,92,84,0.95)]"
        : "border-[rgba(138,149,166,0.22)] bg-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.86)]";

  return (
    <div className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-[rgba(138,149,166,0.14)] bg-[rgba(0,0,0,0.18)] p-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className={`rounded-lg border px-2 py-1 text-[9px] uppercase tracking-[0.16em] ${badge}`}>
            {state}
          </span>
          <div className="text-[11px] font-semibold text-[rgba(226,232,240,0.95)]">{title}</div>
        </div>
        <p className="mt-1 text-[11px] text-[rgba(226,232,240,0.82)]">{body}</p>
      </div>
      {href && cta ? (
        <Link
          href={href}
          className="shrink-0 rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[11px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)]"
        >
          {cta}
        </Link>
      ) : null}
    </div>
  );
}

export function FirstRunChecklistPanel() {
  const [loading, setLoading] = useState(true);
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [providerCount, setProviderCount] = useState<number>(0);
  const [followingCount, setFollowingCount] = useState<number>(0);
  const [inboxCount, setInboxCount] = useState<number>(0);
  const [paperHasFills, setPaperHasFills] = useState<boolean>(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [provRes, folRes, inboxRes, tradesRes] = await Promise.all([
          fetch("/api/platform/providers", { cache: "no-store" }),
          fetch("/api/social/following", { cache: "no-store" }),
          fetch("/api/social/inbox?limit=1", { cache: "no-store" }),
          fetch("/api/paper/trades?limit=1", { cache: "no-store" }),
        ]);

        if (!cancelled) {
          setAuthed(!(provRes.status === 401 || folRes.status === 401 || inboxRes.status === 401 || tradesRes.status === 401));
        }

        const provJson = await provRes.json().catch(() => ({}));
        const folJson = await folRes.json().catch(() => ({}));
        const inboxJson = await inboxRes.json().catch(() => ({}));
        const tradesJson = await tradesRes.json().catch(() => ({}));

        if (!cancelled) {
          setProviderCount(Array.isArray(provJson?.providers) ? provJson.providers.length : 0);
          setFollowingCount(Array.isArray(folJson?.providers) ? folJson.providers.length : 0);
          setInboxCount(Array.isArray(inboxJson?.items) ? inboxJson.items.length : 0);
          setPaperHasFills(Array.isArray(tradesJson?.trades) ? tradesJson.trades.length > 0 : false);
        }
      } catch {
        if (!cancelled) {
          setAuthed(null);
        }
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

    return [
      {
        key: "login",
        state: signedIn ? ("done" as const) : authed === false ? ("todo" as const) : ("todo" as const),
        title: "Sign in",
        body: "Create a session to access approvals, paper portfolio, and publishing keys.",
        href: signedIn ? undefined : "/platform/login",
        cta: signedIn ? undefined : "Sign in",
      },
      {
        key: "provider",
        state: !signedIn ? ("blocked" as const) : hasProvider ? ("done" as const) : ("todo" as const),
        title: "Create publisher (id + key)",
        body: "Create a publisher id and key used to publish results and signals.",
        href: !signedIn ? "/platform/login" : "/platform/providers",
        cta: !signedIn ? "Sign in" : "Open publishing keys",
      },
      {
        key: "publish",
        state: !signedIn ? ("blocked" as const) : hasProvider ? ("todo" as const) : ("blocked" as const),
        title: "Publish a result or signal",
        body: "Use the provider key to publish a leaderboard result and/or a signal update.",
        href: !signedIn ? "/platform/login" : "/platform/providers",
        cta: !signedIn ? "Sign in" : "Copy publish command",
      },
      {
        key: "follow",
        state: !signedIn ? ("blocked" as const) : followsSomeone ? ("done" as const) : ("todo" as const),
        title: "Follow providers",
        body: "Following routes provider updates into your inbox.",
        href: "/leadpage",
        cta: "Browse providers",
      },
      {
        key: "inbox",
        state: !signedIn ? ("blocked" as const) : inboxHas ? ("done" as const) : ("todo" as const),
        title: "Check approvals",
        body: "Approvals shows followed provider ops updates. Approved ops can execute into paper.",
        href: "/inbox",
        cta: "Open approvals",
      },
      {
        key: "paper",
        state: !signedIn ? ("blocked" as const) : hasFills ? ("done" as const) : ("todo" as const),
        title: "Execute → see paper fills",
        body: "Approve an ops intent, then confirm it appears as a fill in your paper portfolio.",
        href: "/paper",
        cta: "Open paper portfolio",
      },
    ] as const;
  }, [authed, followingCount, inboxCount, paperHasFills, providerCount]);

  return (
    <section className="rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-[0.16em] text-[var(--nexus-muted)]">
            First run checklist
          </div>
          <p className="mt-1 text-[11px] text-[rgba(226,232,240,0.82)]">
            {loading ? "Checking your setup…" : "A guided path to a working operator loop."}
          </p>
        </div>
        <div className="text-[10px] text-[var(--nexus-muted)]">
          providers={providerCount} following={followingCount} inbox={inboxCount} fills={paperHasFills ? "yes" : "no"}
        </div>
      </div>

      <div className="mt-3 grid gap-2">
        {steps.map((s) => (
          <StepRow key={s.key} state={s.state} title={s.title} body={s.body} href={s.href} cta={s.cta} />
        ))}
      </div>
    </section>
  );
}

