import { useNavigate } from "react-router";
import { useState } from "react";

export default function PlatformLoginPage({
  embedded = false,
  onAuthed,
  hideEmbeddedHeader = false,
}: {
  embedded?: boolean;
  onAuthed?: () => void;
  hideEmbeddedHeader?: boolean;
}) {
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      if (mode === "register" && password !== confirmPassword) {
        throw new Error("Passwords do not match");
      }
      const res = await fetch(`/api/platform/${mode}`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const json = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || "Auth failed");
      if (embedded) onAuthed?.();
      else navigate("/platform/providers");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Auth failed");
    } finally {
      setBusy(false);
    }
  }

  const canSubmit =
    Boolean(email) &&
    Boolean(password) &&
    (mode === "login" ? true : Boolean(confirmPassword) && password === confirmPassword);

  const shell = (
    <div className={embedded ? "" : "mx-auto w-full max-w-md rounded-2xl border border-border bg-card p-6"}>
      {embedded ? (
        hideEmbeddedHeader ? null : (
          <div className="mb-3">
            <div className="text-sm font-medium text-foreground">{mode === "login" ? "Sign in" : "Create account"}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Use your account to continue.</div>
          </div>
        )
      ) : (
        <>
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">Platform</div>
          <h1 className="mt-1 text-[18px] font-semibold">{mode === "login" ? "Sign in" : "Create account"}</h1>
          <p className="mt-2 text-[12px] text-muted-foreground">
            Sign in to manage providers, publishing keys, approvals, and paper executions.
          </p>
        </>
      )}

        <div className={embedded ? "flex gap-2" : "mt-4 flex gap-2"}>
          <button
            type="button"
            onClick={() => setMode("login")}
            className={`rounded-lg border px-3 py-1.5 text-[12px] transition ${
              mode === "login" ? "border-primary bg-primary/10" : "border-border bg-card hover:bg-muted/30"
            }`}
          >
            Login
          </button>
          <button
            type="button"
            onClick={() => setMode("register")}
            className={`rounded-lg border px-3 py-1.5 text-[12px] transition ${
              mode === "register" ? "border-primary bg-primary/10" : "border-border bg-card hover:bg-muted/30"
            }`}
          >
            Register
          </button>
        </div>

        <div className={embedded ? "mt-3 flex flex-col gap-3" : "mt-4 flex flex-col gap-3"}>
          <input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="email"
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] outline-none"
            autoCapitalize="none"
            autoCorrect="off"
          />
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password"
            type="password"
            className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] outline-none"
          />
          {mode === "register" ? (
            <input
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="confirm password"
              type="password"
              className="w-full rounded-xl border border-border bg-background px-3 py-2 text-[12px] outline-none"
            />
          ) : null}

          {error ? (
            <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
              {error}
            </div>
          ) : null}

          <button
            type="button"
            onClick={submit}
            disabled={busy || !canSubmit}
            className="rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[12px] font-semibold hover:border-[rgba(0,212,170,0.45)] disabled:opacity-50"
          >
            {busy ? "Working…" : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </div>

        {embedded ? null : (
          <p className="mt-4 text-[11px] text-muted-foreground">
            This is for managing provider keys and publishing endpoints. Your trading engine remains separate.
          </p>
        )}
    </div>
  );

  if (embedded) return shell;
  return <div className="flex-1 min-h-0 overflow-auto px-6 py-10">{shell}</div>;
}

