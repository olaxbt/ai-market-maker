import { useEffect, useState } from "react";
import { useSearchParams } from "react-router";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";

function api(path: string) {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `/api${p}`;
}

function errMsg(json: Record<string, unknown>, fallback: string) {
  const d = json?.detail;
  if (typeof d === "string") return d;
  if (d && typeof d === "object") {
    try {
      return JSON.stringify(d);
    } catch {
      return fallback;
    }
  }
  if (typeof json?.error === "string") return json.error;
  return fallback;
}

export default function NexusResearchPanel() {
  const [searchParams] = useSearchParams();
  const runFromUrl = (searchParams.get("run") ?? "").trim();

  const [askRunId, setAskRunId] = useState(runFromUrl);
  const [question, setQuestion] = useState(
    "What were the main drivers of PnL in this run, and what risks would you watch next?",
  );
  const [askLoading, setAskLoading] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [askAnswer, setAskAnswer] = useState<string | null>(null);
  const [askModel, setAskModel] = useState<string | null>(null);

  useEffect(() => {
    if (runFromUrl) setAskRunId(runFromUrl);
  }, [runFromUrl]);

  async function askSupervisor() {
    const rid = askRunId.trim();
    if (!rid) {
      setAskError("Enter a run_id.");
      return;
    }
    const q = question.trim();
    if (!q) {
      setAskError("Enter a question.");
      return;
    }
    setAskError(null);
    setAskAnswer(null);
    setAskModel(null);
    setAskLoading(true);
    try {
      const res = await fetch(api(`/pm/backtests/${encodeURIComponent(rid)}/ask`), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, max_tokens: 600 }),
      });
      const json = (await res.json().catch(() => ({}))) as {
        answer?: string;
        model?: string | null;
        detail?: unknown;
        error?: string;
      };
      if (!res.ok) {
        throw new Error(errMsg(json as Record<string, unknown>, `Ask failed (${res.status})`));
      }
      setAskAnswer(typeof json.answer === "string" ? json.answer : "");
      setAskModel(typeof json.model === "string" ? json.model : null);
    } catch (e: any) {
      setAskError(e?.message || "Supervisor ask failed");
    } finally {
      setAskLoading(false);
    }
  }

  return (
    <Card className="min-h-0">
      <CardHeader className="border-b">
        <CardTitle className="text-[14px]">Supervisor</CardTitle>
        <CardDescription className="text-[12px]">
          Ask questions about a specific run. <code>POST /api/pm/backtests/{"{run_id}"}/ask</code>
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
            <label className="block space-y-1 text-[11px]">
              <span className="text-muted-foreground">run_id</span>
              <input
                value={askRunId}
                onChange={(e) => setAskRunId(e.target.value)}
                placeholder="Paste run id (or use ?run= in URL)"
                className="w-full rounded-xl border border-border bg-card px-3 py-2 font-mono text-[12px] outline-none"
              />
            </label>
            <label className="block space-y-1 text-[11px]">
              <span className="text-muted-foreground">Question</span>
              <textarea
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                rows={4}
                className="w-full resize-y rounded-xl border border-border bg-card px-3 py-2 text-[12px] outline-none"
              />
            </label>
            <button
              type="button"
              disabled={askLoading}
              onClick={() => void askSupervisor()}
              className="rounded-xl border border-[rgba(99,102,241,0.22)] bg-[rgba(99,102,241,0.10)] px-4 py-2 text-[12px] font-semibold text-[rgba(99,102,241,0.95)] hover:bg-[rgba(99,102,241,0.14)] disabled:opacity-40"
            >
              {askLoading ? "Asking…" : "Ask supervisor"}
            </button>
            {askError ? (
              <div className="rounded-xl border border-[rgba(242,92,84,0.28)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[12px] text-[rgba(242,92,84,0.95)]">
                {askError}
              </div>
            ) : null}
            {askAnswer != null ? (
              <div className="space-y-2 rounded-xl border border-border bg-muted/15 p-3 text-[12px] text-foreground/95">
                {askModel ? (
                  <div className="text-[10px] text-muted-foreground">model: {askModel}</div>
                ) : null}
                <div className="whitespace-pre-wrap leading-relaxed">{askAnswer || "(empty)"}</div>
              </div>
            ) : null}
      </CardContent>
    </Card>
  );
}
