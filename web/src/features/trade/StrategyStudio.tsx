"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { BacktestRunResult, TradeRow, EquityPoint } from "@/types/backtest";
import { BacktestEquityChart } from "@/features/backtest/components/BacktestEquityChart";
import { BacktestTradesTable } from "@/components/backtest/BacktestTradesTable";
import { getFlowApiOrigin } from "@/lib/flowApiOrigin";

/* ──────────────────────────────────────────────
   Strategy Studio — AI-powered chat + backtest
   ────────────────────────────────────────────── */

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

interface ChatMessage {
  role: "user" | "assistant" | "system";
  text: string;
}

interface StrategyConfig {
  ticker: string;
  interval_sec: number;
  n_bars: number;
  fee_bps: number;
  initial_cash: number;
  agent_ids: string[];
  description: string;
}

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

export default function StrategyStudio() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "system", text: "Describe your strategy idea in plain language." },
  ]);
  const [chatInput, setChatInput] = useState("");
  const chatEndRef = useRef<HTMLDivElement>(null);
  const [config, setConfig] = useState<StrategyConfig>(DEFAULT_CONFIG);
  const [emotionIndex, setEmotionIndex] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<BacktestRunResult | null>(null);
  const [equityPoints, setEquityPoints] = useState<EquityPoint[]>([]);
  const [trades, setTrades] = useState<TradeRow[]>([]);
  const [viewTab, setViewTab] = useState<"metrics" | "trades">("metrics");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isRunning) return;
    const interval = setInterval(() => setEmotionIndex((i) => (i + 1) % EMOTIONS.length), 800);
    return () => clearInterval(interval);
  }, [isRunning]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

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
      const res = await fetch(`${flowOrigin}/api/backtest/submit`, {
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
        const eqRes = await fetch(`${flowOrigin2}/api/backtests/${btResult.run_id}/equity`);
        if (eqRes.ok) {
          const eqData = await eqRes.json();
          setEquityPoints(eqData.points ?? []);
        }
      } catch { /* ignore */ }

      try {
        const flowOrigin2 = getFlowApiOrigin();
        const trRes = await fetch(`${flowOrigin2}/api/backtests/${btResult.run_id}/trades`);
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

  const handleChatSubmit = useCallback(async () => {
    const text = chatInput.trim();
    if (!text || isRunning) return;
    setChatInput("");

    setMessages((prev) => [...prev, { role: "user", text }]);

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

    try {
      const res = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          conversation: messages.slice(-10).map((m) => ({ role: m.role, text: m.text })),
        }),
      });

      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();

      if (data.action === "configure" && data.config) {
        const c = data.config;
        const newConfig: StrategyConfig = {
          ticker: c.ticker || config.ticker,
          agent_ids: c.agent_ids || config.agent_ids,
          interval_sec: c.interval_sec || config.interval_sec,
          n_bars: c.n_bars || config.n_bars,
          fee_bps: c.fee_bps ?? config.fee_bps,
          initial_cash: c.initial_cash || config.initial_cash,
          description: text,
        };
        setConfig(newConfig);

        const agentList = newConfig.agent_ids.map((id) => `  • ${id}`).join("\n");
        const reply = c.reasoning
          ? `**Strategy blueprint**\nPair: \`${newConfig.ticker}\`\nAgents:\n${agentList}\n\n📝 ${c.reasoning}\n\nSay "run backtest" to execute.`
          : `**Strategy blueprint**\nPair: \`${newConfig.ticker}\`\nAgents:\n${agentList}\n\nSay "run backtest" to execute.`;

        setMessages((prev) => [...prev, { role: "assistant", text: reply }]);
      } else if (data.message) {
        setMessages((prev) => [...prev, { role: "assistant", text: data.message }]);
      }
    } catch {
      const tickerMatch = text.match(/(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)/i);
      const ticker = tickerMatch ? `${tickerMatch[1].toUpperCase()}/USDT` : config.ticker;
      const isTrend = /trend|follow/i.test(text);
      const isReversion = /revert|reversal|mean/i.test(text);
      const agent_ids = isReversion ? ["n6", "n11", "n9"] : isTrend ? ["n4", "n9", "n12"] : config.agent_ids;
      const newConfig = { ...config, ticker, agent_ids };
      setConfig(newConfig);
      setMessages((prev) => [...prev, {
        role: "assistant",
        text: `**Strategy blueprint** (offline)\nPair: \`${ticker}\`\nAgents:\n${agent_ids.map((id) => `  • ${id}`).join("\n")}\n\nSay "run backtest" to execute.`,
      }]);
    }
  }, [chatInput, isRunning, config, messages, runBacktest]);

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

  const metrics = useMemo(() => result?.metrics ?? null, [result]);
  const totalReturn = useMemo(() => {
    if (result?.evaluation?.total_return_pct) return result.evaluation.total_return_pct;
    if (metrics) return ((metrics.final_equity / metrics.initial_cash) - 1) * 100;
    return null;
  }, [result, metrics]);

  return (
    <div className="flex h-full flex-col">
      <div className="flex flex-1 gap-0 overflow-hidden">
        {/* Left: Chat */}
        <div className="flex w-[360px] min-w-[300px] flex-col border-r border-[rgba(138,149,166,0.12)]">
          <div className="flex items-center justify-between border-b border-[rgba(138,149,166,0.12)] px-4 py-2">
            <span className="text-[11px] font-semibold tracking-[0.12em] text-[rgba(226,232,240,0.75)]">CHAT</span>
            <button onClick={() => { setMessages([{ role: "system", text: "Describe your strategy idea in plain language." }]); setResult(null); setEquityPoints([]); setTrades([]); setError(null); }}
              className="rounded-lg border border-[rgba(138,149,166,0.15)] px-2 py-1 text-[10px] text-[rgba(226,232,240,0.55)] hover:border-[rgba(0,212,170,0.3)] hover:text-white">Clear</button>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-2">
            {messages.map((msg, i) => (
              <div key={i} className={`rounded-xl px-3 py-2 text-[11px] leading-relaxed ${
                msg.role === "user"
                  ? "ml-6 bg-[rgba(0,212,170,0.10)] border border-[rgba(0,212,170,0.18)] text-[rgba(226,232,240,0.9)]"
                  : msg.role === "system"
                    ? "bg-[rgba(138,149,166,0.06)] text-[rgba(226,232,240,0.55)] italic"
                    : "mr-6 bg-[rgba(99,102,241,0.08)] border border-[rgba(99,102,241,0.15)] text-[rgba(226,232,240,0.88)]"
              }`}>
                <div className="whitespace-pre-wrap">{msg.text}</div>
              </div>
            ))}
            {isRunning && (
              <div className="mr-6 rounded-xl bg-[rgba(99,102,241,0.08)] border border-[rgba(99,102,241,0.15)] px-3 py-2 text-[11px] text-[rgba(226,232,240,0.7)]">
                <span className="inline-block w-4 mr-1">{EMOTIONS[emotionIndex].icon}</span>
                {EMOTIONS[emotionIndex].label}…
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
          <div className="border-t border-[rgba(138,149,166,0.12)] p-3">
            <div className="flex gap-2">
              <input value={chatInput} onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleChatSubmit()}
                placeholder="Describe your strategy…" disabled={isRunning}
                className="flex-1 rounded-xl border border-[rgba(138,149,166,0.18)] bg-[rgba(6,8,11,0.45)] px-3 py-2 text-[12px] text-white placeholder-[rgba(226,232,240,0.3)] outline-none focus:border-[rgba(0,212,170,0.35)]" />
              <button onClick={handleChatSubmit} disabled={isRunning || !chatInput.trim()}
                className="rounded-xl bg-[rgba(0,212,170,0.15)] px-3 py-2 text-[11px] font-semibold text-[rgba(0,215,170,0.95)] disabled:opacity-30 hover:bg-[rgba(0,212,170,0.22)]">Send</button>
            </div>
          </div>
        </div>

        {/* Right: Canvas */}
        <div className="flex flex-1 flex-col overflow-hidden">
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Templates */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">Templates</div>
              <div className="grid grid-cols-2 gap-2">
                {TEMPLATES.map((t) => (
                  <button key={t.name} onClick={() => loadTemplate(t)}
                    className="rounded-xl border border-[rgba(138,149,166,0.12)] bg-[rgba(6,8,11,0.25)] px-3 py-2 text-left hover:border-[rgba(0,212,170,0.2)]">
                    <div className="text-[11px] font-semibold text-[rgba(226,232,240,0.88)]">{t.name}</div>
                    <div className="mt-0.5 text-[10px] text-[rgba(138,149,166,0.6)]">{t.desc}</div>
                  </button>
                ))}
              </div>
            </section>

            {/* Agents */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">Agents ({config.agent_ids.length}/14)</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(AGENT_NAMES).map(([id, name]) => {
                  const active = config.agent_ids.includes(id);
                  return (
                    <button key={id} onClick={() => toggleAgent(id)}
                      className={`rounded-lg px-2 py-1 text-[10px] font-medium transition-colors ${
                        active
                          ? "border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] text-[rgba(0,215,170,0.9)]"
                          : "border border-[rgba(138,149,166,0.10)] bg-[rgba(6,8,11,0.2)] text-[rgba(138,149,166,0.6)] hover:border-[rgba(138,149,166,0.25)]"
                      }`}>{id}:{name.split(" ")[0]}</button>
                  );
                })}
              </div>
            </section>

            {/* Config */}
            <section>
              <div className="mb-2 text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">Config</div>
              <div className="grid grid-cols-3 gap-2">
                <ConfigField label="Pair" value={config.ticker} onChange={(v) => setConfig((p) => ({ ...p, ticker: v }))} />
                <ConfigField label="Interval" value={`${config.interval_sec}s`} onChange={(v) => setConfig((p) => ({ ...p, interval_sec: parseInt(v) || 3600 }))} />
                <ConfigField label="Bars" value={String(config.n_bars)} onChange={(v) => setConfig((p) => ({ ...p, n_bars: parseInt(v) || 1000 }))} />
                <ConfigField label="Fee (bps)" value={String(config.fee_bps)} onChange={(v) => setConfig((p) => ({ ...p, fee_bps: parseInt(v) || 5 }))} />
                <ConfigField label="Capital ($)" value={String(config.initial_cash)} onChange={(v) => setConfig((p) => ({ ...p, initial_cash: parseInt(v) || 10000 }))} />
              </div>
            </section>

            {/* Run */}
            <button onClick={handleChatSubmit} disabled={isRunning}
              className="w-full rounded-xl border border-[rgba(0,212,170,0.25)] bg-[rgba(0,212,170,0.10)] py-3 text-[12px] font-semibold text-[rgba(226,232,240,0.95)] hover:bg-[rgba(0,212,170,0.17)] disabled:opacity-40">
              {isRunning ? (
                <span className="inline-flex items-center gap-2">
                  <span className="h-3 w-3 animate-spin rounded-full border-2 border-[rgba(0,212,170,0.3)] border-t-[rgba(0,212,170,0.9)]" />
                  Running…
                </span>
              ) : "▶ Run Backtest"}
            </button>

            {/* Results */}
            {result && metrics && (
              <section className="rounded-2xl border border-[rgba(138,149,166,0.15)] bg-[rgba(6,8,11,0.3)] p-4">
                <div className="mb-3 flex items-center justify-between">
                  <div className="text-[10px] uppercase tracking-[0.16em] text-[rgba(138,149,166,0.5)]">Backtest Results — {config.ticker}</div>
                  <div className="flex gap-1">
                    <button onClick={() => setViewTab("metrics")}
                      className={`rounded-lg px-2 py-1 text-[10px] font-medium ${viewTab === "metrics" ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]" : "text-[rgba(138,149,166,0.5)] hover:text-white"}`}>Metrics</button>
                    <button onClick={() => setViewTab("trades")}
                      className={`rounded-lg px-2 py-1 text-[10px] font-medium ${viewTab === "trades" ? "bg-[rgba(0,212,170,0.12)] text-[rgba(0,212,170,0.9)]" : "text-[rgba(138,149,166,0.5)] hover:text-white"}`}>Trades ({trades.length})</button>
                  </div>
                </div>

                {viewTab === "metrics" ? (
                  <div className="space-y-4">
                    <div className="grid grid-cols-5 gap-2">
                      <MetricCard label="Return" value={fmtPct(totalReturn)} color={(totalReturn ?? 0) >= 0 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"} />
                      <MetricCard label="Sharpe" value={fmtN(metrics.sharpe, 2)} color={(metrics.sharpe ?? 0) >= 1 ? "text-[rgba(0,212,170,0.92)]" : "text-[rgba(242,92,84,0.95)]"} />
                      <MetricCard label="Max DD" value={fmtPct(metrics.max_drawdown)} color="text-[rgba(242,92,84,0.8)]" />
                      <MetricCard label="Win Rate" value={`${fmtN(metrics.win_rate, 1)}%`} color="text-[rgba(226,232,240,0.88)]" />
                      <MetricCard label="PF" value={fmtN(metrics.profit_factor, 2)} color="text-[rgba(226,232,240,0.88)]" />
                    </div>
                    {equityPoints.length > 0 && (
                      <div className="h-[200px]">
                        <BacktestEquityChart points={equityPoints} initialCash={config.initial_cash} trades={trades} />
                      </div>
                    )}
                  </div>
                ) : (
                  <BacktestTradesTable trades={trades} />
                )}
              </section>
            )}

            {error && (
              <div className="rounded-xl border border-[rgba(242,92,84,0.2)] bg-[rgba(242,92,84,0.08)] px-3 py-2 text-[11px] text-[rgba(242,92,84,0.9)]">{error}</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
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
