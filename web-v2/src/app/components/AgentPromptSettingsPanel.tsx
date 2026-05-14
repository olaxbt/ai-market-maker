import { useEffect, useMemo, useState } from "react";
import { RotateCcw, Save } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { cn } from "./ui/utils";

type AgentPromptSettings = {
  node_id: string;
  system_prompt: string;
  task_prompt: string;
  model?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  tools?: string[] | null;
  cot_enabled?: boolean | null;
  applies_to_runtime?: boolean | null;
  mode?: string | null;
};

function asStr(v: unknown) {
  return typeof v === "string" ? v : v == null ? "" : String(v);
}

function asNumOrNull(v: unknown): number | null {
  if (typeof v !== "number" || !Number.isFinite(v)) return null;
  return v;
}

function safeJsonParse<T>(raw: string): T | null {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

function flowUnreachableMessage(raw: unknown): string | null {
  const m = String((raw as { message?: string })?.message ?? raw ?? "").toLowerCase();
  if (m.includes("failed to fetch") || m.includes("networkerror") || m.includes("load failed") || m.includes("network request failed")) {
    return "Could not reach the Flow API. Start Flow (default http://127.0.0.1:8001), set VITE_FLOW_API_BASE_URL in web-v2/.env, and use `vite dev` or `vite preview` so `/api` is proxied.";
  }
  return null;
}

export function AgentPromptSettingsPanel({ nodeId }: { nodeId: string | null }) {
  const id = (nodeId ?? "").trim() || null;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<AgentPromptSettings | null>(null);
  const [saving, setSaving] = useState(false);

  const appliesToRuntime = useMemo(() => Boolean(data?.applies_to_runtime), [data]);

  const [systemPrompt, setSystemPrompt] = useState("");
  const [taskPrompt, setTaskPrompt] = useState("");
  const [model, setModel] = useState("");
  const [temperature, setTemperature] = useState<string>("");
  const [maxTokens, setMaxTokens] = useState<string>("");

  const baseline = useMemo(
    () => ({
      system: data?.system_prompt ?? "",
      task: data?.task_prompt ?? "",
      model: data?.model ?? "",
      temperature: data?.temperature ?? null,
      max_tokens: data?.max_tokens ?? null,
    }),
    [data],
  );

  const dirty = useMemo(() => {
    const t = temperature.trim();
    const mt = maxTokens.trim();
    const tempNum = t ? Number(t) : null;
    const maxTokNum = mt ? Number(mt) : null;
    const tempOk = t === "" || (Number.isFinite(tempNum) && tempNum >= 0 && tempNum <= 2);
    const maxTokOk = mt === "" || (Number.isFinite(maxTokNum) && maxTokNum >= 1 && maxTokNum <= 200_000);
    if (!tempOk || !maxTokOk) return true; // treat invalid as dirty so user sees "Save disabled"
    return (
      systemPrompt !== baseline.system ||
      taskPrompt !== baseline.task ||
      model !== (baseline.model ?? "") ||
      (t === "" ? null : tempNum) !== baseline.temperature ||
      (mt === "" ? null : maxTokNum) !== baseline.max_tokens
    );
  }, [baseline, systemPrompt, taskPrompt, model, temperature, maxTokens]);

  const valid = useMemo(() => {
    const t = temperature.trim();
    const mt = maxTokens.trim();
    const tempNum = t ? Number(t) : null;
    const maxTokNum = mt ? Number(mt) : null;
    const tempOk = t === "" || (Number.isFinite(tempNum) && tempNum >= 0 && tempNum <= 2);
    const maxTokOk = mt === "" || (Number.isFinite(maxTokNum) && maxTokNum >= 1 && maxTokNum <= 200_000);
    return tempOk && maxTokOk;
  }, [temperature, maxTokens]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!id) {
        setLoading(false);
        setError(null);
        setData(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/agent-prompts/${encodeURIComponent(id)}`, { cache: "no-store" as any });
        const text = await res.text();
        const json = safeJsonParse<AgentPromptSettings>(text);
        if (!res.ok) {
          const detail = String((json as any)?.detail || (json as any)?.error || text || "").trim();
          throw new Error(
            res.status === 404
              ? detail || `Not found (${id}). Ensure Flow is running and this node exists in NODE_REGISTRY.`
              : detail || text || `HTTP ${res.status}`,
          );
        }
        if (cancelled) return;
        setData(json);
        setSystemPrompt(asStr(json?.system_prompt));
        setTaskPrompt(asStr(json?.task_prompt));
        setModel(asStr(json?.model));
        setTemperature(json?.temperature == null ? "" : String(json.temperature));
        setMaxTokens(json?.max_tokens == null ? "" : String(json.max_tokens));
      } catch (e: unknown) {
        if (!cancelled) {
          setData(null);
          setError(flowUnreachableMessage(e) ?? (e as { message?: string })?.message ?? "Failed to load prompt settings");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    setSaving(false);
    setError(null);
  }, [id]);

  async function save() {
    if (!id || !data) return;
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      const t = temperature.trim();
      const mt = maxTokens.trim();
      const body = {
        system_prompt: systemPrompt,
        task_prompt: taskPrompt,
        model: model.trim() || null,
        temperature: t === "" ? null : Number(t),
        max_tokens: mt === "" ? null : Number(mt),
        tools: data.tools ?? null,
        cot_enabled: data.cot_enabled ?? null,
      };
      const res = await fetch(`/api/agent-prompts/${encodeURIComponent(id)}`, {
        method: "PUT",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      const json = safeJsonParse<AgentPromptSettings>(text);
      if (!res.ok) throw new Error((json as any)?.detail || (json as any)?.error || text || `HTTP ${res.status}`);
      // Rehydrate baseline
      setData((prev) => (prev ? { ...prev, ...json } : json));
      setSystemPrompt(asStr(json?.system_prompt));
      setTaskPrompt(asStr(json?.task_prompt));
      setModel(asStr(json?.model));
      setTemperature(asNumOrNull(json?.temperature) == null ? "" : String(json?.temperature));
      setMaxTokens(asNumOrNull(json?.max_tokens) == null ? "" : String(json?.max_tokens));
    } catch (e: unknown) {
      setError(flowUnreachableMessage(e) ?? (e as { message?: string })?.message ?? "Save failed");
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    if (!data) return;
    setSystemPrompt(asStr(data.system_prompt));
    setTaskPrompt(asStr(data.task_prompt));
    setModel(asStr(data.model));
    setTemperature(data.temperature == null ? "" : String(data.temperature));
    setMaxTokens(data.max_tokens == null ? "" : String(data.max_tokens));
  }

  const tallPromptShell = Boolean(id && data && !loading && !error);

  return (
    <Card
      className={cn(
        "flex flex-col",
        tallPromptShell && "min-h-[min(70vh,640px)] lg:max-h-[min(78vh,720px)]",
      )}
    >
      <CardHeader className="border-b">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-[14px]">Prompt settings</CardTitle>
            <CardDescription className="text-[12px]">
              {id ? (
                <>
                  node <code className="font-mono text-[11px]">{id}</code>
                  {data?.mode ? (
                    <>
                      <span className="mx-2 text-muted-foreground/40">•</span>
                      mode {String(data.mode)}
                    </>
                  ) : null}
                </>
              ) : (
                "Select an agent to view prompt settings."
              )}
            </CardDescription>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={save}
              disabled={!id || !data || saving || !dirty || !valid}
              className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70 disabled:opacity-50"
              title={
                appliesToRuntime
                  ? "Save prompt settings"
                  : "You can save, but it won’t change runtime until the node is LLM-backed"
              }
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              onClick={reset}
              disabled={!id || !data || saving || !dirty}
              className="inline-flex items-center gap-1 rounded-lg border border-border bg-card px-3 py-2 text-xs font-medium hover:bg-muted/70 disabled:opacity-50"
              title="Reset edits"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </button>
          </div>
        </div>
      </CardHeader>
      <CardContent className={cn("gap-3 pt-4", tallPromptShell && "flex min-h-0 flex-1 flex-col overflow-hidden")}>
        {!id ? (
          <div className="rounded-lg border border-dashed border-border bg-muted/20 px-4 py-8 text-center text-sm text-muted-foreground">
            No agent selected.
          </div>
        ) : loading ? (
          <div className="text-sm text-muted-foreground">Loading prompt settings…</div>
        ) : error ? (
          <div className="rounded-md border border-destructive/35 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            {error}
          </div>
        ) : !data ? (
          <div className="rounded-lg border border-border bg-muted/20 px-3 py-2 text-sm text-muted-foreground">
            No prompt settings found for this node.
          </div>
        ) : (
          <>
            {!appliesToRuntime ? (
              <div className="rounded-lg border border-amber-500/25 bg-amber-500/10 px-3 py-2 text-[12px] text-amber-900 dark:text-amber-200">
                This node is deterministic right now. You can still save prompt edits for later, but they won’t affect runtime
                until it’s LLM-backed.
              </div>
            ) : null}

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="mb-1 text-[11px] font-medium text-muted-foreground">System prompt</div>
                <textarea
                  value={systemPrompt}
                  onChange={(e) => setSystemPrompt(e.target.value)}
                  spellCheck={false}
                  className="min-h-[200px] w-full flex-1 resize-y rounded-lg border border-border bg-background px-3 py-2 font-mono text-[12px] leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-60"
                  placeholder="System prompt…"
                />
              </div>
              <div className="flex min-h-[140px] flex-1 flex-col sm:min-h-[160px]">
                <div className="mb-1 text-[11px] font-medium text-muted-foreground">Task prompt</div>
                <textarea
                  value={taskPrompt}
                  onChange={(e) => setTaskPrompt(e.target.value)}
                  spellCheck={false}
                  className="min-h-[160px] w-full flex-1 resize-y rounded-lg border border-border bg-background px-3 py-2 font-mono text-[12px] leading-relaxed outline-none focus-visible:ring-2 focus-visible:ring-ring/40 disabled:opacity-60"
                  placeholder="Task prompt…"
                />
              </div>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

