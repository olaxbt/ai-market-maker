# Persona: Microstructure Agents — 4.1 Whale Behavior Analyst, 4.2 Liquidity & Order Flow (微观结构分析)

## Position
Tier-0 perception cluster covering market microstructure: large-holder behavior and order-book quality. These agents detect whale dump risk and execution quality conditions. Agent 4.1 is disabled by default; enable by setting weight > 0 in agent_weights config.

## Agent Classification

| Agent ID | Code ID | Name | Weight | Default | Class |
|----------|---------|------|--------|---------|-------|
| 4.1 | whale_behavior_analyst | Whale Behavior | 0.05 | Disabled | `WhaleBehaviorAnalystAgent` |
| 4.2 | liquidity_order_flow | Liquidity & Order Flow | 0.15 | Enabled | `LiquidityOrderFlowAgent` |

---

### Agent 4.1 — Whale Behavior Analyst

**Role**: On-chain defense sentinel that monitors whale wallet concentration, large transaction flows, and supply-shock risk. Computes dump probability and sell pressure gauge.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "4.1",
    "ticker": str,
    "status": "success" | "error",
    "Dump_Probability": float,        # [0.0, 1.0] likelihood of whale sell-off
    "Sell_Pressure_Gauge": int,       # [0, 100] cumulative sell pressure from large holders
    "Concentration": float            # optional whale concentration metric
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `dump_probability` | 0.50 | `Dump_Probability` | Inverted: 1.0→0 (high dump = bearish) |
| `concentration_pct` | 0.25 | `Sell_Pressure_Gauge` | Inverted linear |
| `wallet_flow` | 0.25 | Default 0.50 | Not in contract |

---

### Agent 4.2 — Liquidity & Order Flow Analyst

**Role**: Market microstructure analyst evaluating execution quality conditions. Measures slippage risk, order book imbalance, and depth skew to determine whether the market can absorb intended order flow.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "4.2",
    "ticker": str,
    "status": "success" | "error",
    "Slippage_Risk_Score": int,        # [0, 100] higher = worse execution
    "Order_Imbalance": float,          # net order flow imbalance (positive = buy pressure)
    "Depth_Skew": float                # bid/ask depth asymmetry
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `slippage_risk` | 0.35 | `Slippage_Risk_Score` | Inverted: high slippage = bearish |
| `order_imbalance` | 0.35 | `Order_Imbalance` | < 0 → 0.45, else → 0.55 |
| `depth_skew` | 0.30 | Default 0.50 | Not in contract |

## SOP (Both Agents)

1. **Input**: `ticker`, `universe`, `market_data`, optional `nexus_context`
2. **Process**:
   - 4.1: `WhaleBehaviorAnalystAgent.analyze()` — wallet flow, dump probability from on-chain data
   - 4.2: `LiquidityOrderFlowAgent.analyze()` — order book depth, slippage estimation, imbalance detection
3. **Output**: Each agent writes its node-specific payload and appends one entry to `tier0_contracts`
4. **Telemetry**: FlowEvent reasoning entries per agent

## Rules / Constraints
- Agent 4.1 (Whale) is **disabled by default** in v4 config — set weight > 0 in `agent_weights` to enable
- Agent 4.2 (Liquidity) carries weight 0.15 = second-highest single weight after Technical TA
- High Dump_Probability (≥ 0.65) from 4.1 triggers a bearish alignment factor
- High Slippage_Risk_Score (≥ 80) from 4.2 blocks aggressive execution
- Both stubbed when Nexus data unavailable
