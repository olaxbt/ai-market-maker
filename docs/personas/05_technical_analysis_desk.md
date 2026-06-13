# Persona: Technical Analysis Agents — 2.1 Pattern Recognition, 2.2 Statistical Alpha, 2.3 Technical TA (技术分析集群)

## Position
Tier-0 perception cluster encompassing all chart-based, statistical, and classical technical analysis. Together these three agents carry the highest combined weight (0.65) in the weighted convergence arbitrator, making them the dominant factor cluster.

## Agent Classification

| Agent ID | Code ID | Name | Weight | Class |
|----------|---------|------|--------|-------|
| 2.1 | pattern_recognition_bot | Pattern Recognition | 0.25 | `PatternRecognitionBotAgent` |
| 2.2 | statistical_alpha_engine | Statistical Alpha | 0.10 | `StatisticalAlphaEngineAgent` |
| 2.3 | technical_ta_engine | Technical Analysis | 0.30 | `TechnicalTaEngineAgent` |

---

### Agent 2.1 — Pattern Recognition Bot

**Role**: Chart geometry and setup quality analyzer. Identifies technical patterns (cup-and-handle, bull/bear flags, VCP, accumulation/distribution) and computes setup confidence scores.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "2.1",
    "ticker": str,
    "status": "success" | "error",
    "Setup_Score": int,               # [0, 100] setup confidence
    "kalman_support": float | None,   # support level from Kalman filter
    "pattern": str                    # pattern name (accumulation, vcp, bull_flag, etc.)
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `setup_score` | 0.40 | `Setup_Score` | Linear 0→0, 100→1 |
| `pattern_quality` | 0.30 | `pattern` field | Pattern quality mapping (VCP→0.75, distribution→0.30) |
| `timeframe_align` | 0.20 | `kalman_support` presence | 0.55 if support exists, else 0.50 |
| `volume_conf` | 0.10 | `Setup_Score` proxy | Same linear map |

---

### Agent 2.2 — Statistical Alpha Engine

**Role**: Cross-sectional multi-factor analysis. Computes z-scores and alpha signals (Strong Buy / Buy / Hold / Sell / Strong Sell) relative to the trading universe. Determines factor confluence confidence.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "2.2",
    "ticker": str,
    "status": "success" | "error",
    "Factor_Confluence": int,         # [0, 95+] confidence from cross-sectional rank
    "cross_sectional_z_score": float, # [-3.0, 3.0] z-score vs universe
    "alpha_signal": str               # "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell"
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `alpha_signal` | 0.50 | `alpha_signal` | Strong Buy→0.85, Hold→0.50, Strong Sell→0.15 |
| `z_score` | 0.25 | `cross_sectional_z_score` | z=-3→0, z=0→0.5, z=+3→1 |
| `regime_fit` | 0.25 | Default 0.50 | Not in contract, neutral default |

---

### Agent 2.3 — Technical TA Engine

**Role**: Classical TA-Lib technical analysis bundle. Computes RSI, MACD, OBV, ATR, ADX, EMA cross signals, volume, and pattern recognition from OHLCV data.

#### Data Contract
```python
{
    "schema_version": "tier0/v1",
    "agent": "2.3",
    "ticker": str,
    "status": "success" | "error",
    "ta_indicators": {
        "rsi": float,          # [0, 100] relative strength index
        "macd_hist": float,     # MACD histogram value
        "macd": float,          # MACD line
        "macd_signal": float,   # MACD signal line
        "obv": float,           # On-Balance Volume
        "atr": float,           # Average True Range (% of price)
        "adx": float,           # Average Directional Index
        "ema": {"fast": float, "slow": float},
        "volume": float,        # Current volume
        "pattern_rec": float    # Pattern recognition score (optional)
    }
}
```

#### Factor Map
| Factor | Weight | Source | Normalization |
|--------|--------|--------|---------------|
| `rsi` | 0.15 | RSI | Inverted linear: oversold=1, overbought=0 |
| `macd` | 0.20 | MACD histogram | Positive→bullish, negative→bearish |
| `obv` | 0.10 | OBV flow | Positive divergence→bullish |
| `atr` | 0.05 | ATR % | Low=stable(bullish), high=volatile(bearish) |
| `adx` | 0.15 | ADX | 0→0, 25→0.5, 50→1 trending strength |
| `ema_cross` | 0.10 | EMA fast/slow cross | Fast>slow→bullish |
| `volume` | 0.15 | Volume | Linear scale up to 1M |
| `pattern_rec` | 0.10 | Pattern rec score | Raw pass-through |

## SOP (All Three Agents)

1. **Input**: `ticker`, `universe`, `market_data` (and optional `nexus_context` for 2.1/2.2)
2. **Process**:
   - 2.1: `PatternRecognitionBotAgent.analyze()` — pattern identification + setup scoring
   - 2.2: `StatisticalAlphaEngineAgent.analyze()` — cross-sectional z-score, alpha signal
   - 2.3: `TechnicalTaEngineAgent.analyze()` — full TA-Lib bundle from OHLCV
3. **Output**: Each agent writes its node-specific payload and appends one entry to `tier0_contracts`
4. **Telemetry**: FlowEvent reasoning entries per agent with analysis decision

## Rules / Constraints
- Agent 2.3 (Technical TA) has the highest single weight in the system (0.30)
- Combined weight of 2.1 + 2.2 + 2.3 = 0.65 — these three agents dominate the weighted convergence
- All three run in parallel as sibling Tier-0 nodes
- 2.3 does NOT depend on Nexus data (pure OHLCV analysis)
