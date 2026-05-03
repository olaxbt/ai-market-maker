"use client";

import { useState, lazy, Suspense, useMemo } from "react";
import { FlaskConical, Layers, BarChart3, Save, Trash2 } from "lucide-react";

const StrategyStudio = lazy(() => import("@/features/trade/StrategyStudio"));

type StudioPanel = "workspace" | "strategies" | "paper";

const PANELS: { id: StudioPanel; label: string; icon: React.ReactNode }[] = [
  { id: "workspace", label: "Workspace", icon: <FlaskConical className="h-3.5 w-3.5" /> },
  { id: "strategies", label: "My Strategies", icon: <Layers className="h-3.5 w-3.5" /> },
  { id: "paper", label: "Paper Trading", icon: <BarChart3 className="h-3.5 w-3.5" /> },
];

export default function StudioPage() {
  const [activePanel, setActivePanel] = useState<StudioPanel>("workspace");

  return (
    <div className="flex h-[calc(100vh-48px)]">
      {/* ── Left Sidebar ── */}
      <aside className="flex w-[200px] flex-col border-r border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.35)]">
        <div className="flex items-center border-b border-[rgba(138,149,166,0.08)] px-3 py-3 text-[10px] text-[rgba(138,149,166,0.4)]">
          <span>Toolbox</span>
        </div>

        <nav className="flex-1 space-y-0.5 px-1.5 py-3">
          {PANELS.map((p) => (
            <button
              key={p.id}
              onClick={() => setActivePanel(p.id)}
              className={`flex w-full items-center gap-2 rounded-lg px-2 py-2 text-[11px] transition-colors ${
                activePanel === p.id
                  ? "bg-[rgba(0,212,170,0.10)] text-[rgba(0,212,170,0.9)]"
                  : "text-[rgba(138,149,166,0.6)] hover:bg-[rgba(138,149,166,0.06)] hover:text-[rgba(226,232,240,0.8)]"
              }`}
            >
              {p.icon}
              <span>{p.label}</span>
            </button>
          ))}
        </nav>

        <div className="border-t border-[rgba(138,149,166,0.08)] px-3 py-3 space-y-1.5">
          <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] text-[rgba(138,149,166,0.5)] hover:bg-[rgba(138,149,166,0.06)] hover:text-[rgba(226,232,240,0.7)]">
            <Save className="h-3 w-3" />
            Save Draft
          </button>
          <button className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-[10px] text-[rgba(138,149,166,0.5)] hover:bg-[rgba(138,149,166,0.06)] hover:text-[rgba(226,232,240,0.7)]">
            <Trash2 className="h-3 w-3" />
            Reset
          </button>
        </div>
      </aside>

      {/* ── Main content ── */}
      <div className="flex-1 overflow-hidden">
        {activePanel === "workspace" && (
          <Suspense
            fallback={
              <div className="flex h-full items-center justify-center text-[11px] text-[rgba(138,149,166,0.5)]">
                Loading workspace…
              </div>
            }
          >
            <StrategyStudio />
          </Suspense>
        )}
        {activePanel === "strategies" && <MyStrategiesPanel />}
        {activePanel === "paper" && <PaperTradingPanel />}
      </div>
    </div>
  );
}

function MyStrategiesPanel() {
  const mockStrategies = useMemo(
    () => [
      { id: "s1", name: "BTC Trend Follow", asset: "BTC/USDT", created: "2026-04-28", return: 23.4, trades: 247 },
      { id: "s2", name: "ETH Mean Reversion", asset: "ETH/USDT", created: "2026-04-25", return: 15.2, trades: 189 },
      { id: "s3", name: "SOL Momentum", asset: "SOL/USDT", created: "2026-04-20", return: -4.1, trades: 312 },
    ],
    [],
  );

  return (
    <div className="p-6">
      <div className="mb-4 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">
        My Strategies
      </div>
      <div className="space-y-2">
        {mockStrategies.map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between rounded-xl border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.2)] px-4 py-3"
          >
            <div>
              <div className="text-[12px] font-semibold text-[rgba(226,232,240,0.9)]">{s.name}</div>
              <div className="mt-0.5 text-[10px] text-[rgba(138,149,166,0.5)]">
                {s.asset} · {s.created} · {s.trades} trades
              </div>
            </div>
            <div
              className={`text-[13px] font-bold tabular-nums ${
                s.return >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"
              }`}
            >
              {s.return >= 0 ? "+" : ""}
              {s.return}%
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function PaperTradingPanel() {
  return (
    <div className="flex h-full items-center justify-center">
      <div className="text-center">
        <BarChart3 className="mx-auto h-8 w-8 text-[rgba(138,149,166,0.3)]" />
        <div className="mt-3 text-[11px] text-[rgba(138,149,166,0.5)]">
          Paper trading forward tests
        </div>
        <div className="mt-1 text-[10px] text-[rgba(138,149,166,0.35)]">
          Deploy a strategy first to start paper trading.
        </div>
      </div>
    </div>
  );
}
