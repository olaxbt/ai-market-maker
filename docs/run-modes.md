## Run Modes

The system supports three run modes: `backtest`, `paper`, and `live`.  
All modes use the same LangGraph workflow, controlled by a single `run_mode` setting (see `src/config/run_mode.py`).

| Mode      | Purpose                              | Execution / Orders                  |
|-----------|--------------------------------------|-------------------------------------|
| `backtest`| Historical simulation or bar replay  | Simulated fills only (no real keys needed) |
| `paper`   | Default development & testing mode   | Binance testnet (or simulated)      |
| `live`    | Real trading                         | **Real orders** — double-gated (see below) |

### Configuration

- `MODE` — `backtest` \| `paper` \| `live` (default: `paper`)
- `AI_MARKET_MAKER_ALLOW_LIVE` — Must be set to `1`, `true`, or `yes` to enable `live` mode. The process will exit otherwise.
- `STRATEGY_INTERVAL_SEC` — Seconds between full graph runs when using `./start.sh` (default: 180).

You can override the mode for a single run with the CLI:

```bash
uv run python src/main.py --mode paper