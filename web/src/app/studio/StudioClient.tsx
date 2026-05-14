"use client";

import React, { useCallback, useEffect, useRef, useState, lazy, Suspense, useMemo } from "react";
import {
  FlaskConical, Layers, BarChart3, Save, Trash2, Edit2, Play, Check, X, Trophy,
} from "lucide-react";
import { listStrategies, deleteStrategy, renameStrategy, saveStrategy } from "@/lib/strategyStorage";
import type { SavedStrategy } from "@/lib/strategyStorage";

const StrategyStudio = lazy(() => import("@/features/trade/StrategyStudio"));

/* ── Workspace ref handle — StrategyStudio can set this ── */
export interface WorkspaceHandle {
  triggerSave: (name: string) => void;
  triggerReset: () => void;
  getSessionConfig: () => any;
}

type StudioPanel = "workspace" | "strategies";

const PANELS: { id: StudioPanel; label: string; icon: React.ReactNode }[] = [
  { id: "workspace", label: "Workspace", icon: <FlaskConical className="h-3.5 w-3.5" /> },
  { id: "strategies", label: "My Strategies", icon: <Layers className="h-3.5 w-3.5" /> },
];

export default function StudioClient() {
  const [activePanel, setActivePanel] = useState<StudioPanel>("workspace");
  const [loadedStrategy, setLoadedStrategy] = useState<SavedStrategy | null>(null);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const workspaceRef = useRef<WorkspaceHandle | null>(null);

  useEffect(() => {
    // Avoid useSearchParams() build-time CSR bailout.
    const url = new URL(window.location.href);
    const urlPanel = (url.searchParams.get("panel") as StudioPanel | null) ?? null;
    const path = url.pathname;
    const pathPanel: StudioPanel | null =
      path === "/studio/strategies"
        ? "strategies"
          : null;
    setActivePanel(pathPanel ?? urlPanel ?? "workspace");
  }, []);

  const handleLoadStrategy = useCallback((s: SavedStrategy) => {
    setLoadedStrategy(s);
    setActivePanel("workspace");
  }, []);

  const handleWorkspaceSave = useCallback(() => {
    const h = workspaceRef.current;
    if (!h) return;
    const cfg = h.getSessionConfig();
    if (!cfg) return;
    const defaultName = cfg.description
      ? cfg.description.slice(0, 60)
      : `${cfg.ticker} – ${cfg.agent_ids.length} agents`;
    const s = saveStrategy(defaultName, cfg);
    setSaveMsg(`Saved as "${s.name}"`);
    setTimeout(() => setSaveMsg(null), 2500);
  }, []);

  const handleWorkspaceReset = useCallback(() => {
    const h = workspaceRef.current;
    if (h) h.triggerReset();
    setLoadedStrategy(null);
  }, []);

  return (
    <div className="flex h-full min-h-0">
      {/* ── Left Sidebar ── */}
      <aside className="flex w-[220px] flex-col border-r border-[var(--nexus-card-stroke)] bg-[var(--nexus-panel)]/35">
        <div className="flex items-center border-b border-[var(--nexus-rule-soft)] px-3 py-3 text-[10px] text-[var(--nexus-muted)]/70">
          <span>Research Hub</span>
        </div>

        <nav className="flex-1 space-y-0.5 px-1.5 py-3">
          {PANELS.map((p) => (
            <button
              key={p.id}
              onClick={() => setActivePanel(p.id)} data-panel={p.id}
              className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-[11px] transition-colors ${
                activePanel === p.id
                  ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.92)]"
                  : "text-[var(--nexus-muted)]/70 hover:bg-[rgba(138,149,166,0.06)] hover:text-[var(--nexus-text)]"
              }`}
            >
              {p.icon}
              <span>{p.label}</span>
            </button>
          ))}
        </nav>

        <div className="border-t border-[var(--nexus-rule-soft)] px-3 py-3 space-y-1.5">
          <button
            onClick={handleWorkspaceSave}
            disabled={activePanel !== "workspace"}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] text-[var(--nexus-muted)]/70 hover:bg-[rgba(138,149,166,0.06)] hover:text-[var(--nexus-text)] disabled:opacity-30"
          >
            <Save className="h-3 w-3" />
            Save Draft
          </button>
          <button
            onClick={handleWorkspaceReset}
            disabled={activePanel !== "workspace"}
            className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] text-[var(--nexus-muted)]/70 hover:bg-[rgba(138,149,166,0.06)] hover:text-[var(--nexus-text)] disabled:opacity-30"
          >
            <Trash2 className="h-3 w-3" />
            Reset
          </button>
        </div>

        {/* Toast message inside sidebar */}
        {saveMsg && (
          <div className="border-t border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.10)] px-3 py-2 text-[10px] text-[rgba(0,212,170,0.92)]">
            {saveMsg}
          </div>
        )}
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {activePanel === "workspace" && (
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-[11px] text-[var(--nexus-muted)]/70">
                Loading workspace…
              </div>
            }
          >
            <div className="flex-1 min-h-0">
              <StrategyStudio
                initialStrategy={loadedStrategy}
                key={loadedStrategy?.id ?? "default"}
                workspaceRef={workspaceRef}
                onNavigate={(path: string) => {
                  if (path === "panel:strategies") {
                    setActivePanel("strategies");
                  } else if (path === "panel:paper") {
                    window.location.href = "/paper";
                  } else if (path === "panel:leaderboard") {
                    window.location.href = "/leaderboard";
                  } else if (path.startsWith("/")) {
                    window.location.href = path;
                  }
                }}
              />
            </div>
          </Suspense>
        )}
        {activePanel === "strategies" && (
          <div className="flex-1 min-h-0 overflow-auto">
            <MyStrategiesPanel
              onLoad={handleLoadStrategy}
              onDeployToPaper={(s) => {
                handleLoadStrategy(s);
                window.location.href = "/paper";
              }}
            />
          </div>
        )}
      </div>
    </div>
  );
}

function MyStrategiesPanel({ onLoad, onDeployToPaper }: { onLoad: (s: SavedStrategy) => void; onDeployToPaper?: (s: SavedStrategy) => void }) {
  const [refreshKey, setRefreshKey] = useState(0);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const strategies = useMemo(() => listStrategies(), [refreshKey]);

  const handleDelete = useCallback((id: string) => {
    deleteStrategy(id);
    setRefreshKey((k) => k + 1);
  }, []);

  const handleRename = useCallback((id: string) => {
    if (renameValue.trim()) renameStrategy(id, renameValue.trim());
    setRenaming(null);
    setRefreshKey((k) => k + 1);
  }, [renameValue]);

  if (strategies.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-center">
          <Layers className="mx-auto h-8 w-8 text-[rgba(138,149,166,0.3)]" />
          <div className="mt-3 text-[11px] text-[rgba(138,149,166,0.5)]">No saved strategies yet</div>
          <div className="mt-1 text-[10px] text-[rgba(138,149,166,0.35)]">
            Run a backtest in Workspace and click &quot;Save Strategy&quot;.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 overflow-y-auto h-full">
      <div className="mb-4 flex items-center justify-between">
        <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">
          My Strategies ({strategies.length})
        </div>
        <button
          onClick={() => setRefreshKey((k) => k + 1)}
          className="rounded-lg border border-[rgba(138,149,166,0.12)] px-2 py-1 text-[9px] text-[rgba(138,149,166,0.5)] hover:text-white"
        >
          Refresh
        </button>
      </div>
      <div className="space-y-2">
        {strategies.map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between rounded-xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.2)] px-4 py-3"
          >
            <div className="flex-1 min-w-0">
              {renaming === s.id ? (
                <div className="flex items-center gap-2">
                  <input
                    value={renameValue}
                    onChange={(e) => setRenameValue(e.target.value)}
                    autoFocus
                    className="flex-1 rounded-lg border border-[rgba(0,212,170,0.3)] bg-[rgba(6,8,11,0.4)] px-2 py-1 text-[11px] text-white outline-none"
                    onKeyDown={(e) => e.key === "Enter" && handleRename(s.id)}
                  />
                  <button onClick={() => handleRename(s.id)} className="text-[rgba(0,212,170,0.8)]"><Check className="h-3.5 w-3.5" /></button>
                  <button onClick={() => setRenaming(null)} className="text-[rgba(138,149,166,0.5)]"><X className="h-3.5 w-3.5" /></button>
                </div>
              ) : (
                <div>
                  <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.9)]">{s.name}</div>
                  <div className="mt-0.5 text-[10px] text-[rgba(138,149,166,0.5)] truncate">
                    {s.config.ticker} · {s.config.agent_ids.length} agents · {new Date(s.updatedAt).toLocaleDateString()}
                  </div>
                </div>
              )}
            </div>

            {renaming !== s.id && (
              <div className="flex items-center gap-2 shrink-0 ml-3">
                {s.summary && (
                  <div className={`text-[11px] font-bold tabular-nums mr-2 ${
                    (s.summary.total_return_pct ?? 0) >= 0
                      ? "text-[rgba(0,212,170,0.92)]"
                      : "text-[rgba(242,92,84,0.95)]"
                  }`}>
                    {(s.summary.total_return_pct ?? 0) >= 0 ? "+" : ""}
                    {s.summary.total_return_pct?.toFixed(1)}%
                  </div>
                )}
                <button
                  onClick={() => onLoad(s)}
                  title="Load into workspace"
                  className="rounded-lg border border-[rgba(0,212,170,0.15)] bg-[rgba(0,212,170,0.08)] p-1.5 text-[rgba(0,212,170,0.8)] hover:bg-[rgba(0,212,170,0.14)]"
                >
                  <Play className="h-3 w-3" />
                </button>
                <button
                  onClick={() => onDeployToPaper?.(s)}
                  title="Deploy to paper trading"
                  className="rounded-lg border border-[rgba(99,102,241,0.12)] bg-[rgba(99,102,241,0.06)] p-1.5 text-[rgba(99,102,241,0.7)] hover:bg-[rgba(99,102,241,0.12)]"
                >
                  <BarChart3 className="h-3 w-3" />
                </button>
                <button
                  onClick={() => { setRenaming(s.id); setRenameValue(s.name); }}
                  title="Rename"
                  className="rounded-lg border border-[rgba(138,149,166,0.10)] p-1.5 text-[rgba(138,149,166,0.5)] hover:border-[rgba(138,149,166,0.25)] hover:text-white"
                >
                  <Edit2 className="h-3 w-3" />
                </button>
                <button
                  onClick={() => handleDelete(s.id)}
                  title="Delete"
                  className="rounded-lg border border-[rgba(138,149,166,0.10)] p-1.5 text-[rgba(138,149,166,0.45)] hover:border-[rgba(242,92,84,0.3)] hover:text-[rgba(242,92,84,0.8)]"
                >
                  <Trash2 className="h-3 w-3" />
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export type { StudioPanel };

