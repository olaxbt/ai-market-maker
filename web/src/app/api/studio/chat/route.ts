import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/studio/chat
 *
 * Agentic chat endpoint that returns step-by-step actions instead of a
 * single config. The frontend renders each step with tool-call icons,
 * status indicators, and animation delays to create an agentic feel.
 *
 * Supported intents:
 *   strategy_parse — parse NL → config (LLM or keyword fallback)
 *   run_backtest   — signal frontend to execute backtest
 *   show_strategies — navigate to My Strategies panel
 *   show_paper     — navigate to Paper Trading panel
 *   show_leaderboard — navigate to /leaderboard
 *   show_console   — open Nexus console
 *   help           — show available commands
 *   analyze_ticker — real market data fetch from Binance
 *   save_strategy  — save current config
 *   reset          — reset workspace
 */

interface ChatRequest {
  message: string;
  conversation?: { role: string; text: string }[];
}

type Step =
  | { action: "tool_call"; tool: string; text: string }
  | { action: "tool_result"; tool: string; text: string }
  | { action: "update_config"; config: Record<string, any> }
  | { action: "message"; text: string }
  | { action: "navigate"; path: string }
  | { action: "run_backtest" }
  | { action: "reset" };

type StepResponse = { steps: Step[] };

// ── Agent definitions ──

const AGENT_DEFS = [
  { id: "n0", name: "Policy Orchestrator", desc: "Select strategy presets from run history" },
  { id: "n1", name: "Market Scan", desc: "Real-time exchange data, CCXT watchlist" },
  { id: "n2", name: "Monetary Sentinel", desc: "Macro regime detection" },
  { id: "n3", name: "News Narrative Miner", desc: "Event-driven news signals" },
  { id: "n4", name: "Technical Analysis Desk", desc: "TA-Lib patterns, indicators" },
  { id: "n5", name: "Open Interest & Positioning", desc: "OI data, positioning analysis" },
  { id: "n6", name: "Retail Hype Tracker", desc: "Social sentiment, hype detection" },
  { id: "n7", name: "Pro Bias Analyst", desc: "Institutional positioning" },
  { id: "n8", name: "Market Microstructure", desc: "Order flow, liquidity" },
  { id: "n9", name: "Risk Desk", desc: "Risk guard, DD limits, stops" },
  { id: "n10", name: "Desk Debate", desc: "Cross-agent deliberation" },
  { id: "n11", name: "Signal Arbitrator", desc: "Signal validation, conflict resolution" },
  { id: "n12", name: "Portfolio Proposal", desc: "Position sizing, allocation" },
  { id: "n13", name: "Portfolio Execute", desc: "Order generation, broker interface" },
];

const TICKER_SYMBOLS = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK", "MATIC", "ARB", "OP", "SUI", "APT"];

// ── Binance market data fetch ──

interface BinanceTicker {
  symbol: string;
  lastPrice: string;
  priceChangePercent: string;
  volume: string;
  quoteVolume: string;
  highPrice: string;
  lowPrice: string;
  weightedAvgPrice: string;
}

async function fetchBinanceTicker(symbol: string): Promise<BinanceTicker | null> {
  const pair = symbol.replace("/", "");
  try {
    const res = await fetch(
      `https://api.binance.com/api/v3/ticker?symbol=${pair}`,
      { signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

async function fetchBinance24hrStats(symbol: string): Promise<BinanceTicker | null> {
  const pair = symbol.replace("/", "");
  try {
    const res = await fetch(
      `https://api.binance.com/api/v3/ticker/24hr?symbol=${pair}`,
      { signal: AbortSignal.timeout(5000) }
    );
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

// ── Intent detection ──

function detectIntent(text: string, lower: string): string | null {
  if (/^(run|backtest|start|execute|go)\b/i.test(text)) return "run_backtest";
  if (/^(stop|cancel|reset)\b/i.test(text)) return "reset";

  const navPatterns: [RegExp, string][] = [
    [/show\s+(my\s+)?strateg(ies|y)/i, "show_strategies"],
    [/show\s+(my\s+)?paper/i, "show_paper"],
    [/leaderboard|ranking|rank/i, "show_leaderboard"],
    [/console|nexus/i, "show_console"],
    [/help|commands|what can you do|available/i, "help"],
    [/save|store\b/i, "save_strategy"],
  ];

  for (const [re, intent] of navPatterns) {
    if (re.test(text)) return intent;
  }

  const tickerMatch = text.match(/\b(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)\b/i);
  if (tickerMatch && /analyze|price|market|check|look\s*up|status|ticker/i.test(lower)) {
    return "analyze_ticker";
  }

  // Default: parse as strategy
  return "strategy_parse";
}

// ── Help text builder ──

function buildHelpSteps(): Step[] {
  return [
    { action: "tool_call", tool: "help", text: "Loading available commands..." },
    { action: "tool_result", tool: "help", text: "Command index ready." },
    {
      action: "message",
      text: [
        "**Available commands:**",
        "",
        "• Describe a strategy — *\"ETH mean reversion with 4h bars\"*",
        "• `run backtest` — Execute backtest with current config",
        "• `show strategies` — View saved strategies",
        "• `show paper` — Open Paper Trading panel",
        "• `leaderboard` — View leaderboard",
        "• `analyze BTC` — Real-time market analysis",
        "• `save` — Save current strategy configuration",
        "• `reset` — Start fresh",
        "• `help` — This message",
      ].join("\n"),
    },
  ];
}

// ── Analyze ticker steps ──

async function buildAnalyzeTickerSteps(symbol: string): Promise<Step[]> {
  const steps: Step[] = [
    { action: "tool_call", tool: "market_data", text: `Fetching ${symbol}/USDT live data from Binance...` },
  ];

  const pair = `${symbol}/USDT`;
  const [ticker, stats] = await Promise.all([
    fetchBinanceTicker(pair),
    fetchBinance24hrStats(pair),
  ]);

  if (!ticker) {
    steps.push({
      action: "tool_result",
      tool: "market_data",
      text: `Unable to fetch data for ${pair}. Binance API may be unavailable.`,
    });
    steps.push({ action: "message", text: `⚠️ Market data unavailable for ${pair} at this time.` });
    return steps;
  }

  const price = parseFloat(ticker.lastPrice);
  const change24h = stats ? parseFloat(stats.priceChangePercent) : null;
  const vol24h = stats ? parseFloat(stats.quoteVolume) : null;
  const high = stats ? parseFloat(stats.highPrice) : null;
  const low = stats ? parseFloat(stats.lowPrice) : null;

  const trend = change24h !== null
    ? (change24h > 2 ? "bullish ↗" : change24h < -2 ? "bearish ↘" : change24h > 0.5 ? "slightly bullish ↑" : change24h < -0.5 ? "slightly bearish ↓" : "neutral →")
    : "unknown";

  steps.push({
    action: "tool_result",
    tool: "market_data",
    text: `${pair} · $${price.toFixed(2)} · 24h: ${change24h !== null ? change24h.toFixed(2) + "%" : "N/A"} · Trend: ${trend}`,
  });

  const analysisLines = [
    `**${pair} Market Analysis**`,
    ``,
    `Price: \`$${price.toFixed(2)}\`  Trend: \`${trend}\``,
  ];

  if (change24h !== null) analysisLines.push(`24h Change: \`${change24h >= 0 ? "+" : ""}${change24h.toFixed(2)}%\``);
  if (high !== null && low !== null) analysisLines.push(`24h High: \`$${high.toFixed(2)}\`  Low: \`$${low.toFixed(2)}\``);
  if (vol24h !== null) {
    const volStr = vol24h >= 1_000_000_000
      ? `$${(vol24h / 1_000_000_000).toFixed(2)}B`
      : vol24h >= 1_000_000
        ? `$${(vol24h / 1_000_000).toFixed(2)}M`
        : `$${vol24h.toFixed(0)}`;
    analysisLines.push(`24h Volume: \`${volStr}\``);
  }

  analysisLines.push(
    ``,
    `Say *"run backtest"* to execute a strategy on ${pair}, or describe a strategy idea.`
  );

  steps.push({ action: "message", text: analysisLines.join("\n") });
  return steps;
}

// ── Strategy parse steps ──

function buildStrategyParseSteps(text: string, config: Record<string, any>, reasoning: string): Step[] {
  const steps: Step[] = [
    { action: "tool_call", tool: "parse_input", text: "Parsing strategy description..." },
    { action: "tool_result", tool: "parse_input", text: `Intent: strategy configuration for ${config.ticker}` },
    { action: "tool_call", tool: "select_agents", text: "Selecting agent ensemble..." },
    { action: "tool_result", tool: "select_agents", text: `Selected: ${(config.agent_ids as string[]).join(", ")}` },
    { action: "update_config", config },
  ];

  if (reasoning) {
    steps.push({ action: "tool_result", tool: "select_agents", text: reasoning });
  }

  const agentList = (config.agent_ids as string[]).map((id: string) => `  • ${id}`).join("\n");
  const reply = [
    `**Strategy blueprint**`,
    `Pair: \`${config.ticker}\``,
    `Agents:\n${agentList}`,
    ``,
    `Say *"run backtest"* to execute.`,
  ].join("\n");

  steps.push({ action: "message", text: reply });
  return steps;
}

// ── Navigation steps ──

function buildNavigationSteps(path: string, label: string): Step[] {
  return [
    { action: "tool_call", tool: "navigate", text: `Opening ${label}...` },
    { action: "tool_result", tool: "navigate", text: `Navigating to ${label}.` },
    { action: "navigate", path },
  ];
}

// ── Main handler ──

export async function POST(request: NextRequest) {
  try {
    const body: ChatRequest = await request.json();
    const { message, conversation } = body;

    if (!message || typeof message !== "string") {
      return NextResponse.json({ error: "message is required" }, { status: 400 });
    }

    const lower = message.toLowerCase();
    const intent = detectIntent(message, lower);

    // ── Navigation intents (no LLM needed) ──
    if (intent === "show_strategies") {
      return NextResponse.json({ steps: buildNavigationSteps("panel:strategies", "My Strategies") });
    }
    if (intent === "show_paper") {
      return NextResponse.json({ steps: buildNavigationSteps("panel:paper", "Paper Trading") });
    }
    if (intent === "show_leaderboard") {
      return NextResponse.json({ steps: buildNavigationSteps("/leaderboard", "Leaderboard") });
    }
    if (intent === "show_console") {
      return NextResponse.json({ steps: buildNavigationSteps("/console", "Nexus Console") });
    }
    if (intent === "help") {
      return NextResponse.json({ steps: buildHelpSteps() });
    }
    if (intent === "reset") {
      return NextResponse.json({ steps: [{ action: "reset" }] });
    }
    if (intent === "run_backtest") {
      return NextResponse.json({
        steps: [
          { action: "tool_call", tool: "backtest", text: "Executing backtest with current configuration..." },
          { action: "run_backtest" },
        ],
      });
    }
    if (intent === "save_strategy") {
      return NextResponse.json({
        steps: [
          { action: "tool_call", tool: "save", text: "Saving current strategy configuration..." },
          { action: "tool_result", tool: "save", text: "Strategy saved. You can find it in My Strategies panel." },
          { action: "message", text: "✅ Strategy saved. View it in **My Strategies** panel." },
        ],
      });
    }

    // ── analyze_ticker ──
    if (intent === "analyze_ticker") {
      const tickerMatch = message.match(/\b(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)\b/i);
      const symbol = tickerMatch ? tickerMatch[1].toUpperCase() : "BTC";
      const steps = await buildAnalyzeTickerSteps(symbol);
      return NextResponse.json({ steps });
    }

    // ── strategy_parse (default) ──
    // Try LLM first
    const apiKey = process.env.OPENAI_API_KEY || process.env.DEEPSEEK_API_KEY || process.env.AIMM_LLM_KEY;
    const baseUrl = process.env.OPENAI_BASE_URL || "https://api.deepseek.com/v1";
    const model = process.env.OPENAI_MODEL || "deepseek-chat";

    let config: Record<string, any>;
    let reasoning: string;

    if (apiKey) {
      const systemPrompt = `You are a strategy configuration parser for the AI Market Maker system. Convert natural-language trading strategy ideas into structured JSON configs.

Available agents (select 1-7):
${AGENT_DEFS.map((a) => `  ${a.id}: ${a.name} — ${a.desc}`).join("\n")}

Rules:
- Trend: n4 (TA), n9 (Risk), n12 (Portfolio)
- Mean reversion: n6 (Hype), n11 (Arbitrator), n9 (Risk)
- Momentum: n5 (OI), n7 (Pro Bias), n12 (Portfolio)
- Macro/news: n2 (Sentinel), n3 (News)
- Always include n9 (Risk) if trading implied
- n8 (Market Microstructure) for precise entry/exit

Tickers: ${TICKER_SYMBOLS.join(", ")}/USDT

Return ONLY a JSON object with: ticker, agent_ids, interval_sec, n_bars, fee_bps, initial_cash, description, reasoning`;

      const messages: { role: string; content: string }[] = [
        { role: "system", content: systemPrompt },
      ];

      if (conversation) {
        for (const msg of conversation.slice(-6)) {
          messages.push({
            role: msg.role === "user" ? "user" : "assistant",
            content: msg.text,
          });
        }
      }

      messages.push({ role: "user", content: message });

      try {
        const llmRes = await fetch(`${baseUrl.replace(/\/+$/, "")}/chat/completions`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${apiKey}`,
          },
          body: JSON.stringify({ model, messages, temperature: 0.1, max_tokens: 800 }),
        });

        if (llmRes.ok) {
          const llmData = await llmRes.json();
          const content = llmData?.choices?.[0]?.message?.content?.trim() || "";
          const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, content];
          const jsonStr = jsonMatch[1]?.trim() || content;
          const parsed = JSON.parse(jsonStr);
          config = normalizeConfig(parsed, message);
          reasoning = parsed.reasoning || "";
        } else {
          config = parseStrategyKeywords(message);
          reasoning = config.reasoning || "";
        }
      } catch {
        config = parseStrategyKeywords(message);
        reasoning = config.reasoning || "";
      }
    } else {
      config = parseStrategyKeywords(message);
      reasoning = config.reasoning || "";
    }

    const steps = buildStrategyParseSteps(message, config, reasoning);
    return NextResponse.json({ steps });
  } catch (err: any) {
    console.error("Studio chat error:", err);
    return NextResponse.json(
      { steps: [{ action: "message", text: `⚠️ Error: ${err.message}` }] },
      { status: 500 }
    );
  }
}

// ── Helpers ──

function normalizeConfig(raw: Record<string, any>, originalMessage: string): Record<string, any> {
  return {
    ticker: raw.ticker || "BTC/USDT",
    agent_ids: Array.isArray(raw.agent_ids) ? raw.agent_ids : ["n4", "n9", "n12"],
    interval_sec: typeof raw.interval_sec === "number" ? raw.interval_sec : 3600,
    n_bars: typeof raw.n_bars === "number" ? raw.n_bars : 1000,
    fee_bps: typeof raw.fee_bps === "number" ? raw.fee_bps : 5,
    initial_cash: typeof raw.initial_cash === "number" ? raw.initial_cash : 10000,
    description: raw.description || originalMessage,
    reasoning: raw.reasoning || "",
  };
}

function parseStrategyKeywords(text: string): Record<string, any> {
  const lower = text.toLowerCase();
  const tickerMatch = text.match(/\b(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)\b/i);
  const ticker = tickerMatch ? `${tickerMatch[1].toUpperCase()}/USDT` : "BTC/USDT";

  const isTrend = /trend|follow|moving average|ema|sma/i.test(lower);
  const isMeanRev = /mean reversion|reversal|rsi|oversold|overbought|contrarian/i.test(lower);
  const isMomentum = /momentum|breakout|volume|oi|open interest|strength/i.test(lower);
  const isMacro = /macro|news|narrative|sentiment|sentinel|regime|fed|interest rate/i.test(lower);
  const isFull = /full|all|complete|everything|all agents/i.test(lower);

  let agent_ids: string[];
  if (isFull) agent_ids = ["n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12"];
  else if (isTrend) agent_ids = ["n4", "n9", "n12"];
  else if (isMeanRev) agent_ids = ["n6", "n11", "n9"];
  else if (isMomentum) agent_ids = ["n5", "n7", "n12"];
  else if (isMacro) agent_ids = ["n2", "n3", "n9"];
  else agent_ids = ["n4", "n9", "n12"];

  const scalping = /scalp|1m|1min|minute/i.test(lower);
  const dayTrade = /day|5m|15m|short/i.test(lower);
  const swing = /swing|4h|hourly|1h|2h/i.test(lower);
  const position = /position|daily|1d|long.?term/i.test(lower);

  let interval_sec: number;
  if (scalping) interval_sec = 60;
  else if (dayTrade) interval_sec = 900;
  else if (swing) interval_sec = 3600;
  else if (position) interval_sec = 86400;
  else interval_sec = 3600;

  const barsMatch = text.match(/(\d+)\s*(?:bar|candle)/i);
  const n_bars = barsMatch ? parseInt(barsMatch[1]) : 1000;

  const capitalMatch = text.match(/\$(\d[\d,]*)/);
  const initial_cash = capitalMatch ? parseInt(capitalMatch[1].replace(/,/g, "")) : 10000;

  let reasoning: string;
  if (isTrend) reasoning = "Trend-following requires TA analysis (n4), risk guard (n9), and position sizing (n12)";
  else if (isMeanRev) reasoning = "Mean reversion needs hype detection (n6), signal arbitration (n11), and risk guard (n9)";
  else if (isMomentum) reasoning = "Momentum uses OI data (n5), pro bias (n7), and portfolio allocation (n12)";
  else reasoning = "General strategy with TA (n4), risk guard (n9), and portfolio (n12)";

  return { ticker, agent_ids, interval_sec, n_bars, fee_bps: 5, initial_cash, description: text, reasoning };
}
