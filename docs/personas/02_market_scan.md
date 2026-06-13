# Persona: Market Scan (Data Aggregation / 市场扫描器)

## Position
Data aggregation node that fetches and hydrates market data for the primary ticker and universe symbols. Determines universe composition and runs initial market context for Tier-0 agents.

## Agent Classification
- **Agent ID**: N/A (Data)
- **Type**: Data Aggregation
- **Code Class**: `MarketScanAgent` + `market_scan` node function (`src/main.py`)
- **Enabled by default**: Yes

## Goals
- Fetch OHLCV + depth data for primary ticker and universe symbols
- Select and expand the trading universe (env-configured or volume-ranked with OI augmentation)
- Attach Nexus data bundle (`shared_memory["nexus"]`) when Nexus feeds are enabled
- Scan meme coin candidates (paper/live only)

## SOP
1. **Input**: `ticker`, `run_mode`, `shared_memory` from state; `market.scan.*` app settings
2. **Process**:
   - Backtest mode: use provided `market_data`, build universe from configured symbols
   - Paper/live mode: call `MarketScanAgent.fetch_data()` per symbol, use `select_universe_from_tickers()` with optional OI augmentation, attach Nexus depth and global bundle
   - Meme coin scan via `MarketScanAgent.scan_meme_coins()` (paper/live only)
   - Universe pairs computed via combinatorial expansion for correlation analysis
3. **Output**:
   - `market_data` — enriched `{symbol: {ohlcv, nexus_depth, ...}}` dict
   - `universe` — ordered symbol list
   - `universe_pairs` — correlation pairs
   - `market_scan` — meme coin candidates
   - `shared_memory["nexus"]` — Nexus global bundle (when available)
4. **Telemetry**: FlowEvent node_start/node_end; reasoning entry with scan decision

## Data Contract
```python
{
    "ticker": str,
    "universe": [str, ...],       # ordered list of symbols
    "universe_pairs": [[str, str], ...],
    "market_data": {
        "BTC/USDT": {
            "ohlcv": [[ts, o, h, l, c, v], ...],
            "nexus_depth": { ... },
            "status": "success" | "error",
            ...
        },
        ...
    },
    "market_scan": [  # meme candidates (paper/live)
        {"symbol": str, ...},
        ...
    ],
    "shared_memory": {
        "nexus": { ... }  # when nexus_feeds_enabled()
    }
}
```

## Rules / Constraints
- Universe size controlled by `app_settings.market.universe_size` (default ~30)
- Universe symbols configurable via `app_settings.market.universe_symbols`
- Always includes primary ticker first in universe list
- Backtest mode is deterministic and offline-friendly
- Nexus depth fetched per symbol (5 levels, via `get_nexus_adapter()`)
- Meme scan limited to top 2 candidates
