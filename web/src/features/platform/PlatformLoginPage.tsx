"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { NexusSectionHeader } from "@/components/NexusSectionHeader";

export function PlatformLoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/platform/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(json?.detail || json?.error || "Auth failed");
      router.push("/platform/providers");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auth failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <NexusSectionHeader
        title="PLATFORM"
        subtitle="Sign in to manage providers, follows, and executions."
        active="nexus"
      />
      <div className="px-4 py-8">
        <div className="mx-auto w-full max-w-md rounded-2xl border border-[color:var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/55 p-5">
          <h1 className="text-sm font-semibold tracking-wide text-[rgba(226,232,240,0.98)]">
            {mode === "login" ? "Sign in" : "Create account"}
          </h1>

          <div className="mt-4 flex gap-2">
            <button
              type="button"
              onClick={() => setMode("login")}
              className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
                mode === "login" ? "is-active" : ""
              }`}
            >
              Login
            </button>
            <button
              type="button"
              onClick={() => setMode("register")}
              className={`nexus-segment-btn rounded-lg px-3 py-1.5 text-[11px] transition ${
                mode === "register" ? "is-active" : ""
              }`}
            >
              Register
            </button>
          </div>

          <div className="mt-4 flex flex-col gap-3">
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="email"
              className="nexus-prompt-input w-full rounded-xl px-3 py-2 text-[12px]"
              autoCapitalize="none"
              autoCorrect="off"
            />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="password"
              type="password"
              className="nexus-prompt-input w-full rounded-xl px-3 py-2 text-[12px]"
            />

            {error ? (
              <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.95)]">
                {error}
              </div>
            ) : null}

            <button
              type="button"
              onClick={submit}
              disabled={busy || !email || !password}
              className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold text-[rgba(226,232,240,0.95)] hover:border-[rgba(0,212,170,0.45)] disabled:opacity-50"
            >
              {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
            </button>
          </div>

          <p className="mt-4 text-[10px] text-[var(--nexus-muted)]">
            This is for managing provider keys and publishing endpoints. Your trading engine remains
            separate.
          </p>
        </div>
      </div>
    </div>
  );
}
