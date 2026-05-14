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
- `STRATEGY_INTERVAL_SEC` — Seconds between full graph runs for repeated CLI invocations (default: 180).

You can override the mode for a single run with the CLI:

```bash
uv run python src/main.py --mode paper
```

---

## Execution Engine & Exchange Adapters

This section documents the OMS layer and exchange adapter system added in the Hyperliquid OMS adapter PR.

### Execution engine selection

`AI_MARKET_MAKER_EXECUTION_ENGINE` controls which execution path `get_nexus_adapter()` returns.

| Value | Behaviour |
|-------|-----------|
| `legacy` (default) | Returns `NexusAdapter` on the existing paper path — zero behaviour change |
| `oms` | Returns `OmsNexusAdapter` wrapping an `Oms` instance — adds idempotency, lifecycle states, cancel/status/reconcile |

The default is `legacy`. No env var needed for the existing paper path.

### Exchange adapters

| `EXCHANGE` value | Adapter | Status |
|-----------------|---------|--------|
| `paper` (default) | `NexusAdapter` | Fully supported |
| `hyperliquid` | `HyperliquidAdapter` | Dry-run only — see below |

### Hyperliquid adapter status

`HyperliquidAdapter` is present and tested. The following are fully implemented:

- `FakeHyperliquidClient` — pure-Python test double, injectable, no SDK required
- `dry_run=True` path — validates + normalizes orders, returns `status="dry_run"` without calling the exchange
- `_SdkHyperliquidClient` — lazy SDK wrapper; raises `RuntimeError` with clear message if `hyperliquid-python-sdk` is not installed
- Symbol normalization — `"BTC/USDT"` → `"BTC"`, `"ETH-USD"` → `"ETH"`, etc.

**Not implemented in this PR:** `_SdkHyperliquidClient` method bodies are `NotImplementedError` stubs. Real live order placement via the Hyperliquid SDK is intentionally deferred. Attempting it raises `RuntimeError("not implemented")` at startup before any orders are placed.

### Safety model

| Layer | Mechanism |
|-------|-----------|
| Allow-live gate | `AI_MARKET_MAKER_ALLOW_LIVE=1` required for any non-paper exchange |
| Dry-run guard | `HYPERLIQUID_DRY_RUN=1` — `HyperliquidAdapter.place_order()` returns immediately, adapter never called |
| OMS dry-run | `dry_run=True` propagated to `Oms` — order held in `CREATED` state, adapter never called |
| Testnet default | `HYPERLIQUID_TESTNET` defaults to `1` — mainnet requires explicit opt-out |
| Fail-closed | Unsupported live path raises `RuntimeError` at startup, not at order time |
| Secret redaction | `__repr__` on both `HyperliquidAdapter` and `ExchangeConfig` never exposes `hyperliquid_secret` |
| Unknown states | Unrecognised exchange status maps to `OrderState.UNKNOWN` (conservative) |
| Idempotency | `Oms` deduplicates by SHA-256 key — duplicate submit calls return existing order |

### Example configurations

**Default paper mode (no env changes needed):**

```env
# Nothing required — legacy NexusAdapter paper path is the default
AI_MARKET_MAKER_EXECUTION_ENGINE=legacy
```

**OMS paper mode (lifecycle tracking, no real exchange):**

```env
AI_MARKET_MAKER_EXECUTION_ENGINE=oms
EXCHANGE=paper
```

**Hyperliquid dry-run via OMS (supported):**

```env
AI_MARKET_MAKER_EXECUTION_ENGINE=oms
EXCHANGE=hyperliquid
AI_MARKET_MAKER_ALLOW_LIVE=1
HYPERLIQUID_TESTNET=1
HYPERLIQUID_DRY_RUN=1
# No real API key needed for dry-run
```

**Hyperliquid live trading (NOT YET SUPPORTED):**

Real live order placement is blocked until a future PR implements and fully tests `_SdkHyperliquidClient`. Attempting to start without `HYPERLIQUID_DRY_RUN=1` raises:

```
RuntimeError: Hyperliquid live SDK execution is not implemented in this PR.
Set HYPERLIQUID_DRY_RUN=1 to use dry-run mode, or use exchange=paper.
```

---

## OMS Persistent Order Ledger

When `AI_MARKET_MAKER_EXECUTION_ENGINE=oms`, order state lives in memory by default. The ledger layer makes it optional to persist that state to SQLite so it survives process restarts.

### Ledger types

| `AI_MARKET_MAKER_OMS_LEDGER` | Behaviour |
|------------------------------|-----------|
| `in_memory` (default) | No filesystem side-effects — identical to no ledger |
| `sqlite` | Persists `oms_orders` and `oms_order_events` to a local SQLite file |

### What SQLite persistence enables

- **Restart-safe idempotency** — duplicate order submissions blocked across process restarts, not just within a single run
- **Order state recovery** — `ACCEPTED`, `PARTIALLY_FILLED`, and other live orders reload on startup
- **Event audit trail** — every state transition (created, submitted, accepted, cancelled, expired, …) is appended to `oms_order_events` for future reconciliation
- No external services required — uses Python stdlib `sqlite3`

### Schema

**`oms_orders`** — one row per order, upserted on every state change:

| Column | Type | Notes |
|--------|------|-------|
| `client_order_id` | TEXT PK | stable across restarts |
| `idempotency_key` | TEXT UNIQUE | SHA-256 of strategy+run+symbol+side+type+nonce |
| `state` | TEXT | `OrderState` string value |
| `venue_order_id` | TEXT | set after exchange confirms |
| … | | all other `OmsOrder` fields |

**`oms_order_events`** — append-only event log, keyed on `client_order_id`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | INTEGER PK AUTOINCREMENT | insertion order |
| `event_type` | TEXT | `order_created`, `order_submitted`, `order_accepted`, … |
| `payload_json` | TEXT | small JSON payload (no secrets) |
| `created_at` | INTEGER | unix epoch seconds |

### Configuration

```env
AI_MARKET_MAKER_OMS_LEDGER=sqlite
AI_MARKET_MAKER_OMS_SQLITE_PATH=.runs/oms/orders.sqlite   # default path
```

### Safety

- No secrets are written to the ledger — only order metadata already held in `OmsOrder`
- `in_memory` is the default — no SQLite file is created unless explicitly configured
- The SQLite file and its parent directories are created lazily on first use
- WAL journal mode is enabled for crash safety
- This PR still does not implement real Hyperliquid live SDK order placement