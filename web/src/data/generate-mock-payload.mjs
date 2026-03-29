/**
 * Regenerates mock-traces.json — nine-agent NexusPayload with flat message_log + agent_prompts.
 * From `web/`: `npm run generate:mock` (or: `node src/data/generate-mock-payload.mjs`).
 * Not used at runtime; live stack uses Flow API or explicit mock mode.
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(__dirname, "mock-traces.json");

const nodes = [
  { id: "n1", actor: "connectivity", label: "Data Connectivity", status: "COMPLETED", summary: "WS health, drift vs NTP, subscription manifest — no invented prices." },
  { id: "n2", actor: "market-scan", label: "Market Microstructure", status: "COMPLETED", summary: "Spread, depth, imbalance, toxicity — L2/L3 features for fusion." },
  { id: "n3", actor: "price-pattern", label: "Technical Analysis", status: "COMPLETED", summary: "Multi-TF regime, levels, pattern candidates; flags timeframe conflicts." },
  { id: "n4", actor: "sentiment", label: "Sentiment & News", status: "COMPLETED", summary: "Headlines + social velocity, event risk, scored with uncertainty." },
  { id: "n5", actor: "quant", label: "Quant Engine", status: "COMPLETED", summary: "Fuses n2–n4 → scorecard, p_hat, attribution, contradiction_index." },
  { id: "n6", actor: "strategy-planner", label: "Strategy Planner", status: "ACTIVE", summary: "Order intent: grid/ladder, POST_ONLY, size & slippage caps." },
  { id: "n7", actor: "risk-guard", label: "Risk Guard", status: "PENDING", summary: "Veto authority: exposure, Kelly, leverage — APPROVE | REJECT | MODIFY." },
  { id: "n8", actor: "compliance", label: "Compliance Gate", status: "PENDING", summary: "Policy pack, allowlist, lineage tags — audit-ready decisions." },
  { id: "n9", actor: "nexus-executor", label: "Execution Hub", status: "PENDING", summary: "Venue routing, fees/latency model, slices & post-trade state." },
];

const edges = [
  { from: "n1", to: "n2" },
  { from: "n1", to: "n3" },
  { from: "n1", to: "n4" },
  { from: "n2", to: "n5" },
  { from: "n3", to: "n5" },
  { from: "n4", to: "n5" },
  { from: "n5", to: "n6" },
  { from: "n6", to: "n7" },
  { from: "n7", to: "n8" },
  { from: "n8", to: "n9" },
];

/** Full demo prompts — production-style, agent-specific */
const SYSTEM = {
  n1: `You are Data Connectivity for an institutional crypto market-making stack. You own exchange sessions, symbol normalization, websocket subscriptions, and clock skew. Never invent prices; cite feed latency and staleness. Output structured health: venues_ok, drift_ms, subscriptions, last_tick_age_ms. If a venue is degraded, propose failover order. Refuse actions that would double-subscribe or cross-wire accounts.`,
  n2: `You are Market Microstructure. Analyze L2/L3, spread dynamics, queue position estimates, and short-horizon impact. You produce machine-readable features: mid, spread_bps, depth_10bps_usd, imbalance, microprice_shift, toxicity_score. Flag wash-risk and iceberg suspicion. Do not assert directional alpha; describe microstructure state only.`,
  n3: `You are Technical Analysis in a systematic desk context. Multi-timeframe regime labels, volatility buckets, and pattern hypotheses with confidence. Always separate signal from narrative. Emit: regime, key_levels, pattern_candidates[], conflict_notes if timeframes disagree. No trade instructions—hand off scores to Quant.`,
  n4: `You are Sentiment & News. Ingest headlines, social velocity, and entity-linked events. Score sentiment with uncertainty; track event risk (ETF flows, macro prints, exchange incidents). Output: sentiment_score [-1,1], event_risk, source_mix, caveats. Penalize low-source diversity. Never fabricate citations.`,
  n5: `You are the Quant fusion engine. Combine microstructure, TA, and sentiment into a single calibrated scorecard: p_hat, edge_bps_estimate, half_life_s_hint, feature_attribution. Use explicit assumptions and decay. Emit JSON-friendly blocks for Strategy Planner. If inputs conflict, surface contradiction_index and request human review thresholds.`,
  n6: `You are Strategy Planner. Given scorecard and inventory, propose concrete order intent: side, price rules, size, time-in-force, venue preference. Respect min_notional and tick size. You must output an actionable proposal object and rationale chain. Never bypass Risk or Compliance—your output is input to governance agents.`,
  n7: `You are Risk Guard with veto authority. Enforce exposure, leverage, concentration, drawdown gates, and Kelly-derived bounds. You may APPROVE, REJECT, or MODIFY proposals with explicit numeric reasons. Log pre-trade checks as thought steps. If data missing, default to conservative hold.`,
  n8: `You are Compliance Gate. Enforce desk policy: allowed instruments, jurisdictions, reporting flags, and audit metadata. Check that proposal tags include strategy_id and trace lineage. You may block or require amendment. Output compliance_decision and retention hints. No legal advice—policy rules only.`,
  n9: `You are Execution Hub. Route to venues with cost model: fees, latency, fill probability. Produce child orders, cancel/replace logic, and post-trade summary. Minimize information leakage in logs. On partial fills, reconcile and emit execution_state. Never execute without prior APPROVED risk and compliance states in context.`,
};

const TASK = {
  n1: `For ticker {{ticker}} and run {{run_id}}: verify all feeds, print subscription manifest, measure clock drift vs NTP, and emit CONNECTIVITY_REPORT v1.`,
  n2: `Using the latest orderbook snapshots for {{ticker}}, compute microstructure features for the last 5m window and highlight anomalies vs 24h baseline.`,
  n3: `Evaluate {{ticker}} across 1m/15m/4h: regime, volatility percentile, and pattern candidates. Note conflicts between short and medium horizon.`,
  n4: `Scan last 2h of ranked news + social velocity for {{ticker}} and BTC beta. Return sentiment_score, event_risk, and top 3 drivers with uncertainty.`,
  n5: `Fuse inputs from n2–n4 into scorecard v2: p_hat, edge_bps_estimate, attribution vector, contradiction_index. Flag if confidence < 0.55.`,
  n6: `Given scorecard and current inventory, propose the next grid/ladder adjustment or flat decision. Include LIMIT/POST_ONLY params and max_slippage_bps.`,
  n7: `Evaluate the Strategy proposal against limits: max_gross_usd, max_symbol_pct, max_leverage, Kelly cap. Return APPROVE | REJECT | MODIFY with numbers.`,
  n8: `Validate proposal against policy pack v3: instrument allowlist, client_tag, and trace_id lineage. Append compliance_decision JSON.`,
  n9: `If upstream states are APPROVED, build venue routing plan and simulated slippage curve; else return NOOP with reason. Summarize expected fees.`,
};

const tools = {
  n1: ["mcp.exchange.health", "mcp.clock.ntp_delta", "mcp.symbols.normalize"],
  n2: ["mcp.orderbook.snapshot", "mcp.depth.aggregate"],
  n3: ["mcp.ta.features", "mcp.candles.ohlcv"],
  n4: ["mcp.news.stream", "mcp.social.velocity"],
  n5: ["mcp.quant.fuse", "mcp.stats.calibrate"],
  n6: ["mcp.strategy.grid", "mcp.inventory.read"],
  n7: ["mcp.risk.limits", "mcp.portfolio.exposure"],
  n8: ["mcp.policy.pack", "mcp.audit.append"],
  n9: ["mcp.router.quote", "mcp.execution.slice"],
};

function agentPrompts() {
  return nodes.map((n) => ({
    node_id: n.id,
    actor_id: n.actor,
    system_prompt: SYSTEM[n.id],
    task_prompt: TASK[n.id],
    cot_enabled: n.id === "n6" || n.id === "n7",
    model: "gpt-4.1",
    temperature: n.id === "n4" ? 0.35 : 0.15,
    max_tokens: 4096,
    tools: tools[n.id],
  }));
}

function traces() {
  return [
    {
      trace_id: "tx-n1-001",
      node_id: "n1",
      actor: { id: "connectivity", role: "Data Connectivity", persona: "docs/personas/00_connectivity.md" },
      timestamp: "2024-05-20T10:15:21.050Z",
      content: {
        thought_process: [
          { step: 1, label: "Venue ping", detail: "Binance WS RTT p50=14ms p99=38ms; OKX REST 200." },
          { step: 2, label: "Clock skew", detail: "Drift vs NTP +2.1ms (within 10ms budget)." },
          { step: 3, label: "Subscriptions", detail: "BTCUSDT@depth20@100ms + trade streams armed; replay buffer 2s." },
        ],
        context: { pair: "BTC/USDT", signal: "FEEDS_OK", confidence: 0.99 },
      },
    },
    {
      trace_id: "tx-n2-001",
      node_id: "n2",
      parent_id: "tx-n1-001",
      actor: { id: "market-scan", role: "Market Microstructure", persona: "docs/personas/01_market_scanner.md" },
      timestamp: "2024-05-20T10:15:22.100Z",
      content: {
        thought_process: [
          { step: 1, label: "Spread", detail: "spread_bps=1.2 vs 24h median 1.4 — slightly tight." },
          { step: 2, label: "Depth", detail: "depth_10bps_usd=$38.2M bid / $36.9M ask; imbalance +0.018." },
          { step: 3, label: "Toxicity", detail: "toxicity_score=0.22 (low); no sweep clusters in last 60s." },
        ],
        context: { pair: "BTC/USDT", signal: "LIQUIDITY_STRONG", confidence: 0.93 },
      },
    },
    {
      trace_id: "tx-n3-001",
      node_id: "n3",
      parent_id: "tx-n1-001",
      actor: { id: "price-pattern", role: "Technical Analysis", persona: "docs/personas/02_technical.md" },
      timestamp: "2024-05-20T10:15:22.800Z",
      content: {
        thought_process: [
          { step: 1, label: "Regime", detail: "15m: range; 4h: mild uptrend; ADX 18 (weak trend)." },
          { step: 2, label: "Levels", detail: "Resistance 69200–69400; support 67800–68100 from VWAP bands." },
          { step: 3, label: "Conflict", detail: "1m momentum negative while 4h bias positive — contradiction note for Quant." },
        ],
        context: { pair: "BTC/USDT", signal: "REGIME_MIXED", confidence: 0.72 },
      },
    },
    {
      trace_id: "tx-n4-001",
      node_id: "n4",
      parent_id: "tx-n1-001",
      actor: { id: "sentiment", role: "Sentiment & News", persona: "docs/personas/03_sentiment.md" },
      timestamp: "2024-05-20T10:15:23.400Z",
      content: {
        thought_process: [
          { step: 1, label: "Headlines", detail: "ETF flow chatter positive; no fresh exchange FUD in top bucket." },
          { step: 2, label: "Score", detail: "sentiment_score=+0.18 with wide CI (thin macro calendar)." },
          { step: 3, label: "Event risk", detail: "event_risk=LOW; CPI already digested in prior session." },
        ],
        context: { pair: "BTC/USDT", signal: "SENTIMENT_NEUTRAL_PLUS", confidence: 0.61 },
      },
    },
    {
      trace_id: "tx-n5-001",
      node_id: "n5",
      parent_id: "tx-n2-001",
      actor: { id: "quant", role: "Quant Engine", persona: "docs/personas/04_quant.md" },
      timestamp: "2024-05-20T10:15:24.500Z",
      content: {
        thought_process: [
          { step: 1, label: "Fusion", detail: "Microstructure bullish-neutral; TA mixed; sentiment slight positive." },
          { step: 2, label: "Scorecard", detail: "p_hat=0.58 edge_bps_estimate=3.1 contradiction_index=0.31." },
          { step: 3, label: "Attribution", detail: "60% micro, 25% TA, 15% sentiment (by marginal Shapley stub)." },
        ],
        formula: {
          name: "Logit blend",
          latex: "p = \\sigma(w_m z_m + w_t z_t + w_s z_s + b)",
          computed: "p_hat = 0.58",
        },
        context: { pair: "BTC/USDT", signal: "EDGE_MILD_LONG", confidence: 0.58 },
      },
    },
    {
      trace_id: "tx-n6-001",
      node_id: "n6",
      parent_id: "tx-n5-001",
      actor: { id: "strategy-planner", role: "Strategy Planner", persona: "docs/personas/05_strategy.md" },
      timestamp: "2024-05-20T10:15:25.600Z",
      content: {
        thought_process: [
          { step: 1, label: "Inventory", detail: "Net flat +0.02 BTC equiv; no skew emergency." },
          { step: 2, label: "Grid", detail: "Widen inner quotes +2 bps on ask side only; keep POST_ONLY." },
          { step: 3, label: "Safety", detail: "max_slippage_bps=4; cancel stale quotes > 800ms." },
        ],
        proposal: {
          action: "ADJUST_GRID",
          params: {
            symbol: "BTC/USDT",
            bid_spacing_bps: 2.0,
            ask_spacing_bps: 4.0,
            size_clip_btc: 0.35,
            tif: "POST_ONLY",
          },
        },
        context: { pair: "BTC/USDT", signal: "PROPOSE_GRID_TUNE", confidence: 0.76 },
      },
    },
    {
      trace_id: "tx-n7-001",
      node_id: "n7",
      parent_id: "tx-n6-001",
      actor: { id: "risk-guard", role: "Risk Guard", persona: "docs/personas/07_risk_guard.md" },
      timestamp: "2024-05-20T10:15:26.200Z",
      content: {
        thought_process: [
          { step: 1, label: "Gross", detail: "Gross notional 3.1% of cap; per-symbol 1.8% — OK." },
          { step: 2, label: "Kelly", detail: "f* suggest 11.2%; desk cap 12% — within band." },
          { step: 3, label: "Leverage", detail: "Effective lev 3.2x vs limit 5x." },
        ],
        veto_status: { checked_by: "risk-guard", status: "APPROVED", reason: "All gates pass; minor ask widening reduces adverse selection risk." },
      },
    },
    {
      trace_id: "tx-n8-001",
      node_id: "n8",
      parent_id: "tx-n7-001",
      actor: { id: "compliance", role: "Compliance Gate", persona: "docs/personas/08_compliance.md" },
      timestamp: "2024-05-20T10:15:26.900Z",
      content: {
        thought_process: [
          { step: 1, label: "Allowlist", detail: "BTC/USDT on approved symbol map v2024.05." },
          { step: 2, label: "Tags", detail: "strategy_id=GRID-MM-01; trace lineage tx-n6-001 → tx-n7-001 present." },
          { step: 3, label: "Retention", detail: "Log append COMPLIANCE_OK with hash chain slot 0x9f2a…c1." },
        ],
        context: { pair: "BTC/USDT", signal: "COMPLIANCE_OK", confidence: 0.97 },
      },
    },
    {
      trace_id: "tx-n9-001",
      node_id: "n9",
      parent_id: "tx-n8-001",
      actor: { id: "nexus-executor", role: "Execution Hub", persona: "docs/personas/09_execution.md" },
      timestamp: "2024-05-20T10:15:27.500Z",
      content: {
        thought_process: [
          { step: 1, label: "Route", detail: "Primary Binance; backup OKX if spread > 2.5 bps for > 3s." },
          { step: 2, label: "Slicing", detail: "Child clips 0.05 BTC; passive first 70% then IOC remainder." },
          { step: 3, label: "Fees", detail: "Expected maker 2bps / taker 5bps blended ~2.6bps on plan." },
        ],
        context: { pair: "BTC/USDT", signal: "EXEC_PLAN_READY", confidence: 0.88 },
      },
    },
    {
      trace_id: "tx-n5-002",
      node_id: "n5",
      parent_id: "tx-n4-001",
      actor: { id: "quant", role: "Quant Engine", persona: "docs/personas/04_quant.md" },
      timestamp: "2024-05-20T10:15:28.000Z",
      content: {
        thought_process: [
          { step: 1, label: "Stress", detail: "Replay 1% gap down: inventory skew hits soft limit in 7 min at current widen." },
          { step: 2, label: "Recommendation", detail: "Suggest reduce ask size_clip 0.35 → 0.28 if vol percentile > 80." },
        ],
        context: { pair: "BTC/USDT", signal: "STRESS_NOTE", confidence: 0.55 },
      },
    },
    {
      trace_id: "tx-n6-002",
      node_id: "n6",
      parent_id: "tx-n5-002",
      actor: { id: "strategy-planner", role: "Strategy Planner", persona: "docs/personas/05_strategy.md" },
      timestamp: "2024-05-20T10:15:28.600Z",
      content: {
        thought_process: [
          { step: 1, label: "Throttle", detail: "If vol_pct > 80, halve new quote size for 5m window." },
        ],
        proposal: { action: "CONFIG_FLAG", params: { flag: "VOL_THROTTLE", enable: true, window_s: 300 } },
        context: { pair: "BTC/USDT", signal: "DEFENSIVE_MODE", confidence: 0.7 },
      },
    },
  ];
}

function messageLog() {
  const rows = [];
  let seq = 1;
  const push = (ts, node_id, actor_id, kind, message, trace_id) => {
    rows.push({ seq: seq++, ts, node_id, actor_id, kind, message, trace_id });
  };

  push("2024-05-20T10:15:20.100Z", "n1", "connectivity", "status", "RUN_START: binding feeds for BTC/USDT", null);
  push("2024-05-20T10:15:20.220Z", "n1", "connectivity", "tool", "mcp.exchange.health → OK binance,okx", null);
  push("2024-05-20T10:15:20.900Z", "n1", "connectivity", "thought", "Clock drift +2.1ms — within budget", "tx-n1-001");
  push("2024-05-20T10:15:21.050Z", "n1", "connectivity", "handoff", "CONNECTIVITY_REPORT v1 emitted → market-scan", "tx-n1-001");

  push("2024-05-20T10:15:21.200Z", "n2", "market-scan", "status", "Subscribed to depth20@100ms + trades", null);
  push("2024-05-20T10:15:21.950Z", "n2", "market-scan", "thought", "spread_bps=1.2 depth_10bps_usd bid-heavy +0.018", "tx-n2-001");
  push("2024-05-20T10:15:22.100Z", "n2", "market-scan", "handoff", "Microstructure features → quant", "tx-n2-001");

  push("2024-05-20T10:15:22.200Z", "n3", "price-pattern", "thought", "15m range vs 4h uptrend — flag contradiction", "tx-n3-001");
  push("2024-05-20T10:15:22.800Z", "n3", "price-pattern", "handoff", "TA bundle → quant", "tx-n3-001");

  push("2024-05-20T10:15:22.500Z", "n4", "sentiment", "tool", "mcp.news.stream batch 120 headlines scored", null);
  push("2024-05-20T10:15:23.400Z", "n4", "sentiment", "thought", "sentiment_score=+0.18 event_risk LOW", "tx-n4-001");
  push("2024-05-20T10:15:23.500Z", "n4", "sentiment", "handoff", "Sentiment → quant", "tx-n4-001");

  push("2024-05-20T10:15:24.200Z", "n5", "quant", "thought", "Fusing n2/n3/n4 — p_hat=0.58 contradiction_index=0.31", "tx-n5-001");
  push("2024-05-20T10:15:24.500Z", "n5", "quant", "handoff", "Scorecard v2 → strategy-planner", "tx-n5-001");

  push("2024-05-20T10:15:25.100Z", "n6", "strategy-planner", "thought", "Grid tune: widen ask +2bps POST_ONLY", "tx-n6-001");
  push("2024-05-20T10:15:25.600Z", "n6", "strategy-planner", "handoff", "ADJUST_GRID proposal → risk-guard", "tx-n6-001");

  push("2024-05-20T10:15:26.050Z", "n7", "risk-guard", "thought", "Gross 3.1% Kelly 11.2% — APPROVED", "tx-n7-001");
  push("2024-05-20T10:15:26.200Z", "n7", "risk-guard", "handoff", "Risk OK → compliance", "tx-n7-001");

  push("2024-05-20T10:15:26.500Z", "n8", "compliance", "thought", "Allowlist + lineage OK", "tx-n8-001");
  push("2024-05-20T10:15:26.900Z", "n8", "compliance", "handoff", "COMPLIANCE_OK → execution", "tx-n8-001");

  push("2024-05-20T10:15:27.200Z", "n9", "nexus-executor", "thought", "Route Binance primary; clip 0.05 BTC", "tx-n9-001");
  push("2024-05-20T10:15:27.500Z", "n9", "nexus-executor", "status", "EXEC_PLAN_READY (simulation)", "tx-n9-001");

  push("2024-05-20T10:15:27.800Z", "n5", "quant", "thought", "Stress replay note: reduce clip if vol>80pct", "tx-n5-002");
  push("2024-05-20T10:15:28.600Z", "n6", "strategy-planner", "thought", "VOL_THROTTLE flag armed 300s", "tx-n6-002");

  push("2024-05-20T10:15:29.000Z", "n1", "connectivity", "status", "HEARTBEAT tick_age=42ms", null);
  push("2024-05-20T10:15:29.200Z", "n2", "market-scan", "status", "BOOK_REFRESH 50ms", null);

  return rows;
}

const payload = {
  metadata: {
    run_id: "run-BTC-USDT-1732000000",
    ticker: "BTC/USDT",
    status: "LIVE_TRADING",
    version: "0.2.0-nexus-nine",
    pid: 28491,
    kpis: {
      pnl_usd: 9951,
      win_rate_pct: 78.1,
      sharpe_ratio: 2.66,
      latency_ms: 3,
      kelly_pct: 12.4,
      opex_saved: 3900000,
    },
  },
  topology: { nodes, edges },
  traces: traces(),
  agent_prompts: agentPrompts(),
  message_log: messageLog(),
};

fs.writeFileSync(out, JSON.stringify(payload, null, 2) + "\n", "utf8");
console.log("Wrote", out, "nodes=", nodes.length, "traces=", payload.traces.length, "log=", payload.message_log.length);
