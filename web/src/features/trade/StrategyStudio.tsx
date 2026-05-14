"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { BacktestRunResult, TradeRow, EquityPoint } from "@/types/backtest";
import { BacktestEquityChart } from "@/features/backtest/components/BacktestEquityChart";
import { BacktestTradesTable } from "@/components/backtest/BacktestTradesTable";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";
import { saveStrategy, deleteStrategy, renameStrategy } from "@/lib/strategyStorage";
import type { StrategyConfig } from "@/lib/strategyStorage";
import type { WorkspaceHandle } from "@/app/studio/StudioClient";
import Link from "next/link";
import {
  Save, Trash2, Check, X,
  Search, BarChart3, Shield, Activity, Brain, TrendingUp,
  Layers, Terminal, HelpCircle, MapPin,
} from "lucide-react";

/* ──────────────────────────────────────────────
   Strategy Studio — AI-powered chat + backtest
   ────────────────────────────────────────────── */

// ── New message types ──

type ChatMsg =
  | { role: "user" | "system"; text: string }
  | { role: "assistant"; text: string }
  | { role: "tool_call"; tool: string; status: "pending" | "running" | "done" | "error"; text: string };

// ── Tool icon registry ──

const TOOL_ICONS: Record<string, { icon: React.ReactNode; label: string }> = {
  parse_input:     { icon: <Brain className="h-3 w-3" />,            label: "Parse Input" },
  select_agents:   { icon: <Layers className="h-3 w-3" />,            label: "Agent Selection" },
  market_data:     { icon: <BarChart3 className="h-3 w-3" />,         label: "Market Data" },
  analyze_market:  { icon: <TrendingUp className="h-3 w-3" />,       label: "Market Analysis" },
  backtest:        { icon: <Activity className="h-3 w-3" />,          label: "Backtest" },
  execution_plan:  { icon: <Layers className="h-3 w-3" />,            label: "Execution Plan" },
  explain_system:  { icon: <HelpCircle className="h-3 w-3" />,        label: "Explain System" },
  navigate:        { icon: <MapPin className="h-3 w-3" />,            label: "Navigate" },
  save:            { icon: <Save className="h-3 w-3" />,              label: "Save" },
  help:            { icon: <HelpCircle className="h-3 w-3" />,        label: "Help" },
  risk:            { icon: <Shield className="h-3 w-3" />,            label: "Risk Check" },
  console:         { icon: <Terminal className="h-3 w-3" />,          label: "Console" },
};
const DEFAULT_TOOL_ICON = <Activity className="h-3 w-3" />;

// ── Status dot colors ──

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-[rgba(138,149,166,0.4)]",
  running: "bg-[rgba(99,102,241,0.9)]",
  done:    "bg-[rgba(0,212,170,0.9)]",
  error:   "bg-[rgba(242,92,84,0.9)]",
};

const AGENT_NAMES: Record<string, string> = {
  n0: "Policy Orchestrator",
  n1: "Market Scan",
  n2: "Monetary Sentinel",
  n3: "News Narrative Miner",
  n4: "Technical Analysis Desk",
  n5: "Open Interest & Positioning",
  n6: "Retail Hype Tracker",
  n7: "Pro Bias Analyst",
  n8: "Market Microstructure",
  n9: "Risk Desk",
  n10: "Desk Debate",
  n11: "Signal Arbitrator",
  n12: "Portfolio Proposal",
  n13: "Agent OI Positioning",
};

const DEFAULT_CONFIG: StrategyConfig = {
  ticker: "BTC/USDT",
  interval_sec: 3600,
  n_bars: 1000,
  fee_bps: 5,
  initial_cash: 10_000,
  agent_ids: ["n0", "n4", "n9"],
  description: "",
};

const EMOTIONS = [
  { icon: "📊", label: "analyzing" },
  { icon: "⚡", label: "signals detected" },
  { icon: "🛡️", label: "risk guard" },
  { icon: "🔍", label: "microstructure" },
  { icon: "🧠", label: "deliberating" },
  { icon: "📈", label: "trend confirmed" },
];

const TEMPLATES = [
  { name: "BTC Trend Follow", desc: "n4 + n9 — trend with risk guard", config: { ...DEFAULT_CONFIG, ticker: "BTC/USDT", agent_ids: ["n4", "n9", "n12"] } },
  { name: "ETH Mean Reversion", desc: "n6 + n11 — hype + arbitrator", config: { ...DEFAULT_CONFIG, ticker: "ETH/USDT", agent_ids: ["n6", "n11", "n9"] } },
  { name: "SOL Momentum", desc: "n5 + n7 — OI + pro bias", config: { ...DEFAULT_CONFIG, ticker: "SOL/USDT", agent_ids: ["n5", "n7", "n12"] } },
  { name: "Full 14-Agent", desc: "all agents — max deliberation", config: { ...DEFAULT_CONFIG, agent_ids: Object.keys(AGENT_NAMES).filter(k => k !== "n13") } },
];

const STEP_DELAY_MS = 350;
const REPO_URL = "https://github.com/olaxbt/ai-market-maker";

export default function StrategyStudio({
  initialStrategy,
  workspaceRef,
  onNavigate,
}: {
  initialStrategy?: any;
  workspaceRef?: React.MutableRefObject<WorkspaceHandle | null>;
  onNavigate?: (path: string) => void;
}) {
  const [messages, setMessages] = useState<ChatMsg[]>([
    {
      role: "system",
      text:
        "Welcome to Studio.\n\nIf you’re using a hosted demo, I can **answer questions** and **guide you** — but to run the full system (backtests, worker, paper runs) you should clone the repo and run locally.\n\nTry: `onboarding` (recommended), `help`, `publish to leaderboard`, `leaderboard`, or describe a strategy idea.",
    },
  ]);
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const savedConfig = useMemo(() => initialStrategy ? initialStrategy.config : null, [initialStrategy]);
  const [config, setConfig] = useState<StrategyConfig>(savedConfig ?? DEFAULT_CONFIG);
  const [emotionIndex, setEmotionIndex] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BacktestRunResult | null>(null);
  const [equityPoints, setEquityPoints] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [viewTab, setViewTab] = useState<"metrics" | "trades">("metrics");
  const [error, setError] = useState<string | null>(null);
  const [showSaveDialog, setShowSaveDialog] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [saved, setSaved] = useState(false);
  const [animating, setAnimating] = useState(false);
  const abortRef = useRef(false);

  // Expose workspace handle to parent sidebar
  const sessionConfig = useMemo(() => config, [config]);
  useEffect(() => {
    if (workspaceRef) {
      workspaceRef.current = {
        triggerSave: (name: string) => {
          const s = saveStrategy(name || config.description || `${config.ticker}`, config, result?.metrics ?? null);
          setSaved(true);
          setTimeout(() => setSaved(false), 2000);
        },
        triggerReset: () => {
          setConfig(DEFAULT_CONFIG);
          setResult(null);
          setEquityPoints([]);
          setTrades([]);
          setError(null);
          setMessages([
            {
              role: "system",
              text:
                "Welcome to Studio.\n\nIf you’re using a hosted demo, I can **answer questions** and **guide you** — but to run the full system (backtests, worker, paper runs) you should clone the repo and run locally.\n\nTry: `onboarding` (recommended), `help`, `publish to leaderboard`, `leaderboard`, or describe a strategy idea.",
            },
          ]);
        },
        getSessionConfig: () => sessionConfig,
      };
    }
    return () => {
      if (workspaceRef) workspaceRef.current = null;
    };
  }, [workspaceRef, config, result, sessionConfig]);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => setEmotionIndex((i) => (i + 1) % EMOTIONS.length), 800);
    return () => clearInterval(interval);
  }, [isRunning]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Step animator ──
  // Processes a list of steps sequentially with delays, adding messages
  const animateSteps = useCallback(async (steps: any[]) => {
    if (!steps || steps.length === 0) return;

    abortRef.current = false;
    setAnimating(true);

    for (const step of steps) {
      if (abortRef.current) break;

      if (step.action === "tool_call") {
        const tool = step.tool || "unknown";
        setMessages((prev) => [
          ...prev,
          { role: "tool_call" as const, tool, status: "running" as const, text: step.text },
        ]);
      } else if (step.action === "tool_result") {
        // Add as done tool_call
        setMessages((prev) => [
          ...prev,
          { role: "tool_call" as const, tool: step.tool, status: "done" as const, text: step.text },
        ]);
      } else if (step.action === "update_config" && step.config) {
        const c = step.config;
        const newConfig: StrategyConfig = {
          ticker: c.ticker || config.ticker,
          agent_ids: c.agent_ids || config.agent_ids,
          interval_sec: c.interval_sec || config.interval_sec,
          n_bars: c.n_bars || config.n_bars,
          fee_bps: c.fee_bps ?? config.fee_bps,
          initial_cash: c.initial_cash || config.initial_cash,
          description: c.description || '',
        };
        setConfig(newConfig);
      } else if (step.action === "message") {
        // Hide tool_call "pending" and transition the last tool_call to "done" if it was still running
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "tool_call" && last.status === "running") {
            (last as any).status = "done";
          }
          return copy;
        });
        setMessages((prev) => [
          ...prev,
          { role: "assistant" as const, text: step.text },
        ]);
      } else if (step.action === "navigate") {
        if (onNavigate && step.path) {
          onNavigate(step.path);
        }
      } else if (step.action === "run_backtest") {
        // Execute backtest after the current animation chain
        // The tool_call status needs to be set to "done" first
        setMessages((prev) => {
          const copy = [...prev];
          const last = copy[copy.length - 1];
          if (last?.role === "tool_call" && last.status === "running") {
            (last as any).status = "done";
          }
          return copy;
        });
        await sleep(50);
        if (!abortRef.current) {
          runBacktest();
        }
        return; // runBacktest handles its own messages
      } else if (step.action === "reset") {
        setConfig(DEFAULT_CONFIG);
        setResult(null);
        setEquityPoints([]);
        setTrades([]);
        setError(null);
        // Don't clear messages here, add a system message
        setMessages((prev) => [...prev, { role: "system", text: "Workspace reset. Describe a new strategy." }]);
      }

      await sleep(STEP_DELAY_MS);
    }

    setAnimating(false);
  }, [config, onNavigate]);

  // Capture text for update_config reference
  const textRef = useRef("");
  useEffect(() => {
    textRef.current = chatInput;
  }, [chatInput]);

  const runBacktest = useCallback(async () => {
    setIsRunning(true);
    setError(null);
    setResult(null);
    setEquityPoints([]);
    setTrades([]);
    setViewTab("metrics");

    setMessages((prev) => [...prev, {
      role: "assistant",
      text: `Running backtest on ${config.ticker} (${config.agent_ids.length} agents, ${config.n_bars} bars)…`,
    }]);

    try {
      const flowOrigin = getFlowApiOrigin();
      const res = await fetch(`${flowOrigin}/backtests/quick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticker: config.ticker,
          interval_sec: config.interval_sec,
          n_bars: config.n_bars,
          fee_bps: config.fee_bps,
          initial_cash: config.initial_cash,
          agent_ids: config.agent_ids,
          max_steps: config.n_bars,
        }),
      });

      if (!res.ok) {
        const errText = await res.text().catch(() => "unknown error");
        throw new Error(`Backtest failed: ${res.status} ${errText}`);
      }

      const btResult: BacktestRunResult = await res.json();
      setResult(btResult);

      // Fetch equity curve and trades separately
      try {
        const flowOrigin2 = getFlowApiOrigin();
        const eqRes = await fetch(`${flowOrigin2}/backtests/${btResult.run_id}/equity`);
        if (eqRes.ok) {
          const eqData = await eqRes.json();
          setEquityPoints(eqData.points ?? []);
        }
      } catch { /* ignore */ }

      try {
        const flowOrigin2 = getFlowApiOrigin();
        const trRes = await fetch(`${flowOrigin2}/backtests/${btResult.run_id}/trades`);
        if (trRes.ok) {
          const trData = await trRes.json();
          setTrades(trData.trades ?? []);
        }
      } catch { /* ignore */ }

      const m = btResult.metrics;
      const retPct = btResult.evaluation?.total_return_pct
        ?? (m ? ((m.final_equity / m.initial_cash) - 1) * 100 : 0);
      const tradeCount = btResult.trade_count ?? btResult.evaluation?.trade_count ?? 0;

      setMessages((prev) => [...prev, {
        role: "assistant",
        text:
          `**✅ Backtest complete — ${config.ticker}**\n\n` +
          `Return: \`${fmtPct(retPct)}\`  ` +
          `Sharpe: \`${fmtN(m?.sharpe, 2)}\`  ` +
          `DD: \`${fmtPct(m?.max_drawdown)}\`\n` +
          `Trades: \`${tradeCount}\`  ` +
          `Win Rate: \`${fmtN(m?.win_rate, 1)}%\`  ` +
          `PF: \`${fmtN(m?.profit_factor, 2)}\`\n\n` +
          `View full metrics and trade list below.`,
      }]);
    } catch (err: any) {
      setMessages((prev) => [...prev, { role: "assistant", text: `❌ Error: ${err.message}` }]);
      setError(err.message);
    } finally {
      setIsRunning(false);
    }
  }, [config]);

  // ── Chat submit (rewritten for agentic steps) ──

  const handleChatSubmit = useCallback(async () => {
    const text = chatInput.trim();
    if (!text || isRunning || animating) return;
    setChatInput("");

    // Add user message
    setMessages((prev) => [...prev, { role: "user", text }]);

    // Short-circuit: explicit run backtest / reset
    if (/^(run|backtest|start|execute|go)\b/i.test(text)) {
      await runBacktest();
      return;
    }
    if (/^(stop|cancel|reset)\b/i.test(text)) {
      setConfig(DEFAULT_CONFIG);
      setResult(null);
      setEquityPoints([]);
      setTrades([]);
      setError(null);
      setMessages((prev) => [...prev, { role: "system", text: "Reset complete." }]);
      return;
    }

    // Call API for step-based response
    try {
      const res = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation: messages.slice(-10).map((m) => ({ role: m.role, text: "text" in m ? m.text : "" })),
        }),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);

      const data = await res.json();

      if (data.steps && Array.isArray(data.steps)) {
        await animateSteps(data.steps);
      } else if (data.message) {
        setMessages((prev) => [...prev, { role: "assistant", text: data.message }]);
      }
    } catch {
      // Fallback: basic offline parsing
      const tickerMatch = text.match(/(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)/i);
      const ticker = tickerMatch ? `${tickerMatch[1].toUpperCase()}/USDT` : config.ticker;
      const isTrend = /trend|follow/i.test(text);
      const isReversion = /revert|reversal|mean/i.test(text);
      const agent_ids = isReversion ? ["n6", "n11", "n9"] : isTrend ? ["n4", "n9", "n12"] : config.agent_ids;
      const newConfig = { ...config, ticker, agent_ids };
      setConfig(newConfig);

      // Create fallback steps
      await animateSteps([
        { action: "tool_call", tool: "parse_input", text: "Parsing strategy description (offline mode)..." },
        { action: "tool_result", tool: "parse_input", text: `Intent: strategy configuration for ${ticker}` },
        { action: "tool_call", tool: "select_agents", text: "Selecting agent ensemble..." },
        { action: "tool_result", tool: "select_agents", text: `Selected: ${agent_ids.join(", ")}` },
        { action: "update_config", config: newConfig },
        { action: "message", text: `**Strategy blueprint** (offline)\nPair: \`${ticker}\`\nAgents:\n${agent_ids.map((id: string) => `  • ${id}`).join("\n")}\n\nSay "run backtest" to execute.` },
      ]);
    }
  }, [chatInput, isRunning, animating, config, messages, runBacktest, animateSteps]);

  const toggleAgent = useCallback((id: string) => {
    setConfig((prev) => ({
      ...prev,
      agent_ids: prev.agent_ids.includes(id)
        ? prev.agent_ids.filter((a) => a !== id)
        : [...prev.agent_ids, id],
    }));
  }, []);

  const loadTemplate = useCallback((t: typeof TEMPLATES[0]) => {
    setConfig(t.config);
    setResult(null);
    setEquityPoints([]);
    setTrades([]);
    setMessages((prev) => [...prev, { role: "system", text: `Template loaded: **${t.name}**` }]);
  }, []);

  const handleSave = useCallback(() => {
    if (saved) return;
    const defaultName = config.description
      ? config.description.slice(0, 60)
      : `${config.ticker} - ${config.agent_ids.length} agents`;
    setSaveName(defaultName);
    setShowSaveDialog(true);
  }, [config, saved]);

  const confirmSave = useCallback(() => {
    const s = saveStrategy(saveName || `Strategy ${Date.now()}`, config, result?.metrics ?? null);
    setSaved(true);
    setShowSaveDialog(false);
    setTimeout(() => setSaved(false), 2000);
  }, [saveName, config, result]);

  const handleDelete = useCallback((id: string) => {
    deleteStrategy(id);
    setMessages((prev) => [...prev, { role: "system", text: "Strategy deleted." }]);
  }, []);

  const metrics = useMemo(() => result?.metrics ?? null, [result]);
  const totalReturn = useMemo(() => {
    if (result?.evaluation?.total_return_pct) return result.evaluation.total_return_pct;
    if (metrics) return ((metrics.final_equity / metrics.initial_cash) - 1) * 100;
    return null;
  }, [result, metrics]);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-1 min-h-0 gap-0 overflow-hidden">
        {/* Chat-first canvas (no persistent right-side panels) */}
        <div className="flex w-full h-full min-h-0 flex-col">
          <div className="flex items-center justify-between border-b border-[rgba(138,149,166,0.12)] px-4 py-2">
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-semibold tracking-[0.12em] text-[rgba(226,232,240,0.75)]">STUDIO CHAT</span>
              <span className="text-[10px] text-[rgba(138,149,166,0.55)]">Ask anything about the system, then act on it.</span>
            </div>
            <button
              onClick={() => {
                setMessages([
                  {
                    role: "system",
                    text:
                      "I can help you navigate the system end-to-end: design strategies, run backtests, and publish results to the leaderboard.\n\nTry: `help`, `onboarding`, `publish to leaderboard`, `leaderboard`, or describe a strategy idea.",
                  },
                ]);
                setResult(null);
                setEquityPoints([]);
                setTrades([]);
                setError(null);
              }}
              className="rounded-lg border border-[rgba(138,149,166,0.15)] px-2 py-1 text-[10px] text-[rgba(226,232,240,0.55)] hover:border-[rgba(0,212,170,0.3)] hover:text-white"
            >
              Clear
            </button>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto p-4 space-y-3">
            {/* Inline templates as a chat block (not a persistent side panel) */}
            <div className="rounded-2xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.18)] p-3">
              <div className="mb-2 flex items-center justify-between gap-3">
                <div>
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.55)]">Quick templates</div>
                  <div className="mt-0.5 text-[10px] text-[rgba(138,149,166,0.6)]">
                    Pick one, then say <span className="font-mono text-[rgba(226,232,240,0.75)]">run backtest</span>.
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setMessages((prev) => [...prev, { role: "user", text: "help" }])}
                  className="rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.18)] px-2.5 py-1 text-[10px] text-[rgba(138,149,166,0.65)] hover:text-[rgba(226,232,240,0.9)]"
                >
                  Commands
                </button>
              </div>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Link
                  href="/get-started"
                  className="rounded-xl border border-[rgba(0,212,170,0.18)] bg-[rgba(0,212,170,0.08)] px-2.5 py-1 text-[10px] text-[rgba(0,212,170,0.9)] hover:bg-[rgba(0,212,170,0.12)]"
                >
                  Get Started
                </Link>
                <a
                  href={REPO_URL}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.18)] px-2.5 py-1 text-[10px] text-[rgba(138,149,166,0.75)] hover:text-[rgba(226,232,240,0.9)]"
                >
                  GitHub
                </a>
                <Link
                  href="/tools"
                  className="rounded-xl border border-[rgba(99,102,241,0.16)] bg-[rgba(99,102,241,0.06)] px-2.5 py-1 text-[10px] text-[rgba(99,102,241,0.9)] hover:bg-[rgba(99,102,241,0.10)]"
                >
                  Tool Browser
                </Link>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {TEMPLATES.map((t) => (
                  <button
                    key={t.name}
                    onClick={() => loadTemplate(t)}
                    className="group relative overflow-hidden rounded-2xl border border-[rgba(138,149,166,0.14)] bg-[rgba(6,8,11,0.22)] px-3 py-2.5 text-left transition hover:border-[rgba(0,212,170,0.22)] hover:bg-[rgba(6,8,11,0.28)]"
                  >
                    <div
                      className="pointer-events-none absolute inset-0 opacity-0 transition group-hover:opacity-100"
                      style={{
                        background:
                          "radial-gradient(800px circle at 20% -10%, rgba(0,212,170,0.10), transparent 45%), radial-gradient(600px circle at 110% 120%, rgba(34,211,238,0.08), transparent 55%)",
                      }}
                    />
                    <div className="relative">
                      <div className="text-[11px] font-semibold text-[rgba(226,232,240,0.92)]">{t.name}</div>
                      <div className="mt-0.5 text-[10px] text-[rgba(138,149,166,0.65)]">{t.desc}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {messages.map((msg, i) => (
              <ChatMessageBubble key={i} msg={msg} isAnimating={animating && isLastToolRunning(messages, i)} />
            ))}
            {isRunning && !animating && (
              <div className="mr-6 rounded-xl bg-[rgba(99,102,241,0.08)] border border-[rgba(99,102,241,0.15)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.7)]">
                <span className="inline-block w-4 mr-1">{EMOTIONS[emotionIndex].icon}</span>
                {EMOTIONS[emotionIndex].label}…
              </div>
            )}
            <div ref={chatEndRef} />
          </div>

          <div className="border-t border-[rgba(138,149,166,0.12)] p-3 shrink-0">
            <div className="flex gap-2">
              <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleChatSubmit()}
                placeholder={animating ? "Agent working..." : "Ask anything… (e.g. onboarding, publish to leaderboard, analyze BTC)"}
                disabled={isRunning || animating}
                className="flex-1 rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.45)] px-3 py-2 text-[12px] text-white placeholder-[rgba(226,232,240,0.3)] outline-none focus:border-[rgba(0,212,170,0.35)] disabled:opacity-40" />
              <button onClick={handleChatSubmit} disabled={isRunning || animating || !chatInput.trim()}
                className="rounded-xl bg-[rgba(0,212,170,0.15)] px-3 py-2 text-[11px] font-semibold text-[rgba(0,215,170,0.95)] disabled:opacity-30 hover:bg-[rgba(0,212,170,0.22)]">Send</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── ChatMessageBubble component ── */

function ChatMessageBubble({ msg, isAnimating }: { msg: ChatMsg; isAnimating: boolean }) {
  if (msg.role === "tool_call") {
    const iconMeta = TOOL_ICONS[msg.tool] || { icon: DEFAULT_TOOL_ICON, label: msg.tool };
    const statusColor = STATUS_COLORS[msg.status] || STATUS_COLORS.pending;
    const isRunning_ = msg.status === "running" || (msg.status === "pending" && isAnimating);

    return (
      <div className={`rounded-xl px-3 py-2 text-[11px] leading-relaxed border ${
        isRunning_
          ? "bg-[rgba(99,102,241,0.12)] border-[rgba(99,102,241,0.25)]"
          : msg.status === "done"
            ? "bg-[rgba(0,212,170,0.06)] border-[rgba(0,212,170,0.12)] text-[rgba(226,232,240,0.8)]"
            : "bg-[rgba(138,149,166,0.06)] border-[rgba(138,149,166,0.1)] text-[rgba(226,232,240,0.6)]"
      }`}>
        <div className="flex items-center gap-2">
          <span className="shrink-0">
            {iconMeta.icon}
          </span>
          <span className="text-[10px] font-medium tracking-wide text-[rgba(138,149,166,0.7)] uppercase">
            {iconMeta.label}
          </span>
          <span className="ml-auto shrink-0 flex items-center gap-1">
            <span className={`inline-block h-2 w-2 rounded-full ${statusColor} ${isRunning_ ? "animate-pulse" : ""}`} />
            <span className="text-[9px] text-[rgba(138,149,166,0.4)]">
              {msg.status === "pending" ? "pending" : msg.status === "running" ? "running" : msg.status === "done" ? "done" : "error"}
            </span>
          </span>
        </div>
        <div className="mt-1 text-[11px] text-[rgba(226,232,240,0.75)] leading-relaxed">
          {msg.text}
        </div>
      </div>
    );
  }

  // user / assistant / system
  const align =
    msg.role === "user"
      ? "flex justify-end"
      : "flex justify-start";

  return (
    <div className={align}>
      <div
        className={`rounded-2xl px-3 py-2 text-[11px] leading-relaxed break-words ${
          msg.role === "user"
            ? "max-w-[82%] bg-[rgba(0,212,170,0.10)] border border-[rgba(0,212,170,0.18)] text-[rgba(226,232,240,0.9)]"
            : msg.role === "system"
              ? "max-w-[92%] bg-[rgba(138,149,166,0.06)] border border-[rgba(138,149,166,0.10)] text-[rgba(226,232,240,0.55)] italic"
              : "max-w-[82%] bg-[rgba(99,102,241,0.08)] border border-[rgba(99,102,241,0.15)] text-[rgba(226,232,240,0.88)]"
        }`}
      >
        {msg.role === "user" ? (
          <div className="whitespace-pre-wrap break-words overflow-hidden">{msg.text}</div>
        ) : (
          <div className="prose prose-invert max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0 prose-pre:my-2 prose-pre:bg-[rgba(6,8,11,0.45)] prose-pre:border prose-pre:border-[rgba(138,149,166,0.18)] prose-code:text-[rgba(226,232,240,0.92)]">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Helpers ── */

function isLastToolRunning(messages: ChatMsg[], index: number): boolean {
  for (let i = messages.length - 1; i >= 0; i--) {
    const m = messages[i];
    if (m.role === "tool_call" && (m.status === "running" || m.status === "pending")) {
      return i === index;
    }
  }
  return false;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* ── Sub-components ── */

function ConfigField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-0.5">
      <span className="text-[9px] text-[rgba(138,149,166,0.5)]">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-lg border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.3)] px-2 py-1 text-[11px] font-mono text-[rgba(226,232,240,0.88)] outline-none focus:border-[rgba(0,212,170,0.25)]" />
    </label>
  );
}

function MetricCard({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="rounded-xl border border-[rgba(138,149,166,0.08)] bg-[rgba(6,8,11,0.35)] px-3 py-2">
      <div className="text-[9px] text-[rgba(138,149,166,0.5)]">{label}</div>
      <div className={`mt-0.5 text-[13px] font-bold tabular-nums ${color}`}>{value}</div>
    </div>
  );
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtN(v: number | null | undefined, d: number): string {
  if (v == null) return "—";
  return v.toFixed(d);
}