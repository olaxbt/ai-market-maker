import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/studio/chat
 *
 * Takes a natural-language strategy description and returns a structured
 * strategy configuration (agents, ticker, parameters) that matches our
 * 14-agent AIMM system.
 *
 * This endpoint proxies to an LLM (DeepSeek API) for strategy parsing,
 * then returns a structured JSON config that the frontend applies.
 */

interface ChatRequest {
  message: string;
  conversation?: { role: string; text: string }[];
}

interface StructuredConfig {
  ticker: string;
  interval_sec: number;
  n_bars: number;
  fee_bps: number;
  initial_cash: number;
  agent_ids: string[];
  description: string;
  reasoning: string;
}

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

const SYSTEM_PROMPT = `You are a strategy configuration parser for the AI Market Maker system. Your task is to convert a user's natural-language trading strategy idea into a structured JSON configuration.

Available agents (select 1-7 based on strategy needs):
${AGENT_DEFS.map((a) => `  ${a.id}: ${a.name} — ${a.desc}`).join("\n")}

Rules for agent selection:
- Trend following: n4 (TA), n9 (Risk), n12 (Portfolio)
- Mean reversion: n6 (Hype), n11 (Arbitrator), n9 (Risk)
- Momentum: n5 (OI), n7 (Pro Bias), n12 (Portfolio)
- Macro/news: n2 (Sentinel), n3 (News)
- Full system: n0 + n1 + n2 + n3 + n4 + n5 + n6 + n7 + n8 + n9 + n10 + n11 + n12
- Always include n9 (Risk Desk) if real trading is implied
- n0 (Policy Orchestrator) only if strategy type selection is needed
- n10 (Desk Debate) when multiple conflicting signals expected
- n8 (Market Microstructure) for precise entry/exit timing

Available tickers: ${TICKER_SYMBOLS.join(", ")}/USDT

Default intervals (choose based on strategy style):
- 60 (1min) for scalping, 300 (5min) for day trading
- 900 (15min) for swing, 3600 (1H) for trend
- 14400 (4H) for position, 86400 (1D) for long-term

Return ONLY valid JSON with this structure:
{
  "ticker": "BTC/USDT",
  "agent_ids": ["n4", "n9", "n12"],
  "interval_sec": 3600,
  "n_bars": 1000,
  "fee_bps": 5,
  "initial_cash": 10000,
  "description": "brief description of the understood strategy",
  "reasoning": "brief explanation of why these agents were chosen"
}`;

export async function POST(request: NextRequest) {
  try {
    const body: ChatRequest = await request.json();
    const { message, conversation } = body;

    if (!message || typeof message !== "string") {
      return NextResponse.json({ error: "message is required" }, { status: 400 });
    }

    // Short-circuit: if user says "run" or "backtest", return signal to execute
    if (/^(run|backtest|start|execute|go)\b/i.test(message.trim())) {
      return NextResponse.json({
        action: "run_backtest",
        message: "Executing backtest with current configuration.",
      });
    }

    if (/^(stop|cancel|reset)\b/i.test(message.trim())) {
      return NextResponse.json({
        action: "reset",
        message: "Configuration reset. Describe a new strategy.",
      });
    }

    // Build conversation history for context
    const messages: { role: string; content: string }[] = [
      { role: "system", content: SYSTEM_PROMPT },
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

    // Call LLM via server-side env var (OpenAI-compatible)
    const apiKey = process.env.OPENAI_API_KEY || process.env.DEEPSEEK_API_KEY || process.env.AIMM_LLM_KEY;
    const baseUrl = process.env.OPENAI_BASE_URL || "https://api.deepseek.com/v1";
    const model = process.env.OPENAI_MODEL || "deepseek-chat";

    if (!apiKey) {
      // Fallback: basic keyword parsing when no LLM key is available
      return NextResponse.json({
        action: "configure",
        config: parseStrategyKeywords(message),
        message: "Basic configuration applied. To unlock AI parsing, set OPENAI_API_KEY or DEEPSEEK_API_KEY in your .env.",
      });
    }

    const llmRes = await fetch(`${baseUrl.replace(/\/+$/, "")}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.1,
        max_tokens: 800,
      }),
    });

    if (!llmRes.ok) {
      const errText = await llmRes.text().catch(() => "LLM error");
      console.error("Studio chat LLM error:", llmRes.status, errText);
      // Fallback to keyword parser
      return NextResponse.json({
        action: "configure",
        config: parseStrategyKeywords(message),
      });
    }

    const llmData = await llmRes.json();
    const content = llmData?.choices?.[0]?.message?.content?.trim() || "";

    // Extract JSON from response (handle markdown-wrapped JSON)
    let config: Partial<StructuredConfig>;
    try {
      const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)```/) || [null, content];
      const jsonStr = jsonMatch[1]?.trim() || content;
      config = JSON.parse(jsonStr);
    } catch {
      config = parseStrategyKeywords(message);
    }

    return NextResponse.json({
      action: "configure",
      config: {
        ticker: config.ticker || "BTC/USDT",
        agent_ids: config.agent_ids || ["n4", "n9", "n12"],
        interval_sec: config.interval_sec || 3600,
        n_bars: config.n_bars || 1000,
        fee_bps: config.fee_bps || 5,
        initial_cash: config.initial_cash || 10000,
        description: config.description || message,
        reasoning: config.reasoning || "",
      },
    });
  } catch (err: any) {
    console.error("Studio chat error:", err);
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}

/**
 * Fallback: basic keyword-based strategy parser when LLM is unavailable.
 */
function parseStrategyKeywords(text: string): Partial<StructuredConfig> {
  const lower = text.toLowerCase();
  const tickerMatch = text.match(/\b(BTC|ETH|SOL|BNB|XRP|ADA|DOGE|AVAX|DOT|LINK|MATIC|ARB|OP|SUI|APT)\b/i);
  const ticker = tickerMatch ? `${tickerMatch[1].toUpperCase()}/USDT` : "BTC/USDT";

  // Determine strategy style
  const isTrend = /trend|follow|moving average|ema|sma/i.test(lower);
  const isMeanRev = /mean reversion|reversal|rsi|oversold|overbought|contrarian/i.test(lower);
  const isMomentum = /momentum|breakout|volume|oi|open interest|strength/i.test(lower);
  const isMacro = /macro|news|narrative|sentiment|sentinel|regime|fed|interest rate/i.test(lower);
  const isFull = /full|all|complete|everything|all agents/i.test(lower);

  let agent_ids: string[];
  if (isFull) {
    agent_ids = ["n0", "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n10", "n11", "n12"];
  } else if (isTrend) {
    agent_ids = ["n4", "n9", "n12"];
  } else if (isMeanRev) {
    agent_ids = ["n6", "n11", "n9"];
  } else if (isMomentum) {
    agent_ids = ["n5", "n7", "n12"];
  } else if (isMacro) {
    agent_ids = ["n2", "n3", "n9"];
  } else {
    agent_ids = ["n4", "n9", "n12"];
  }

  // Determine timeframe
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

  // Extract bar count
  const barsMatch = text.match(/(\d+)\s*(?:bar|candle)/i);
  const n_bars = barsMatch ? parseInt(barsMatch[1]) : 1000;

  // Extract capital
  const capitalMatch = text.match(/\$(\d[\d,]*)/);
  const initial_cash = capitalMatch ? parseInt(capitalMatch[1].replace(/,/g, "")) : 10000;

  return {
    ticker,
    agent_ids,
    interval_sec,
    n_bars,
    fee_bps: 5,
    initial_cash,
    description: text,
    reasoning: isTrend ? "Trend-following requires TA analysis (n4), risk guard (n9), and position sizing (n12)"
      : isMeanRev ? "Mean reversion needs hype detection (n6), signal arbitration (n11), and risk guard (n9)"
      : isMomentum ? "Momentum uses OI data (n5), pro bias (n7), and portfolio allocation (n12)"
      : "General strategy with TA (n4), risk guard (n9), and portfolio (n12)",
  };
}
