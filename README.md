# AI Market Maker: Agentic Trading System for Crypto Hedge Funds (OpenClaw Ready) 🦀

**AI-Market-Maker** is an **OpenClaw-ready**, agentic trading stack for crypto hedge funds. Built specifically for the OpenClaw ecosystem and **Korean Claw Community approved**, this system combines specialist AI trading agents (acting as trading desks), LangGraph orchestration, and hard Risk Guard veto power.

**Korean Claw Community Approved** 🎯 - This project follows the community's best practices for OpenClaw integration and agentic workflow design.

### Key Features
- **OpenClaw Native** - Pre-packaged as Claw skill with one-click installation
- **Agentic Architecture** - 7 specialized trading agents as autonomous desks
- **Korean Community Approved** - Following Claw community best practices
- **Multi-agent workflow** with clear desk responsibilities
- **Strict Risk Guard** that can veto any trade
- **Quant-style backtesting** with built-in benchmarks (excess return vs buy-and-hold)
- **Unified agent interface** + governance layer
- **Paper trading** on Binance Testnet + rich local backtester
- **Modern web dashboard** for telemetry and traces
- **Clean configuration** (JSON policy + env for secrets only)

---

## Goals

**Current (Trading Mode)**  
Fetch real-time data, generate signals through specialist agents, run portfolio logic, apply Risk Guard veto, and execute on Binance Testnet.

**Near-term**  
Full position lifecycle, multi-asset portfolio management, configurable leverage, and improved long/short handling.

**Longer-term**  
Deeper agentic capabilities, better OpenClaw integration, and support for additional execution venues and data sources.

---

## Why This Project Stands Out

- **Real risk governance** — Risk Guard has final veto power, not just logging.
- **Quant discipline** — Every backtest includes clear benchmarks. No hand-waving.
- **Standardized agents** — All agents follow the same `Input → Process → Output → Feedback` contract.
- **Transparency** — Full traces, reasoning logs, and event ledger.
- **Extensibility** — Built with LangGraph, clean personas, and OpenClaw skill packaging.

## System Architecture

The workflow mimics a small hedge fund:

1. **Research Desks** — Market Scan, Technical Analysis, Statistical Alpha, Sentiment
2. **Alpha Generation** — Signal synthesis and thesis building
3. **Portfolio Management** — Risk-weighted allocation and trade sizing
4. **Risk Guard** — Final safety layer (can veto everything)
5. **Execution** — Only proceeds if Risk Guard approves  

<img width="784" height="1138" alt="workflow_diagram" src="https://github.com/user-attachments/assets/fcf5d491-7562-4acc-8499-3d93d24d395b" />

See **[docs/langgraph-workflow.md](docs/langgraph-workflow.md)** for the complete graph state, nodes, edges and routing logic.

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker

# 2. Install dependencies
pip install uv

# 3. Install TA-Lib first (see installation options in Prerequisites section)
# Example using Conda (recommended for OpenClaw environments):
# wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
# bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda
# source $HOME/miniconda/bin/activate
# conda install -y ta-lib -c conda-forge

# 4. Install Python dependencies
uv sync --extra dev
uv run pre-commit install

# 3. Set up environment
cp .env.example .env
# Edit .env with your API keys (Binance Testnet + OpenAI recommended)

# 4. Run the full stack (API + strategy + web UI)
./start.sh
```

Open http://localhost:3000 to view the dashboard.

For CLI-only trading mode:
```bash
uv run python src/main.py
```

---

## Setup Details

### Prerequisites
- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- **TA-Lib (C library + Python wrapper)** - see installation options below
- Binance Testnet API keys (for paper trading)
- OpenAI API key (optional, enables LLM nodes)
- (Optional) Nexus Skills API access

#### TA-Lib Installation Options

**Option 1: Conda (Recommended)**
```bash
# Install Miniconda if not already installed
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p $HOME/miniconda
source $HOME/miniconda/bin/activate
conda install -y ta-lib -c conda-forge
```

**Option 2: System Package Manager**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y ta-lib

# macOS (Homebrew)
brew install ta-lib

# Then install Python wrapper
pip install ta-lib
```

**Option 3: Source Compilation**
```bash
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr/local
make
sudo make install
pip install ta-lib
```

**Note for OpenClaw Users:** If running in OpenClaw environment without sudo privileges, use Option 1 (Conda) as shown in the CI workflow.

### Configuration Philosophy
- **Policy & universe** → `config/policy.default.json` and `config/app.default.json` (single source of truth)
- **Secrets** → only in `.env`

Detailed docs:
- [`docs/configuration.md`](docs/configuration.md)
- [`docs/policy-schema.md`](docs/policy-schema.md)
- [`docs/run-modes.md`](docs/run-modes.md)

### Testing

```bash
# Default unit tests (no network)
uv run pytest -q

# Full agentic E2E tests
uv run pytest -q tests/test_agentic_trading_e2e.py tests/test_tier0_consensus.py
```

---

## Agents (Desks)

- **Market Scan** — New listings, momentum, universe coverage
- **Technical TA Engine** — Pattern recognition, MACD, indicators
- **Statistical Alpha Engine** — Factor and cross-sectional signals
- **Sentiment & Narrative** — News, retail hype, whale behavior
- **Risk Management** — Position sizing, volatility-based limits
- **Portfolio Management** — Multi-asset allocation and proposal generation
- **Risk Guard** — Hard veto layer before execution

All agents follow a standardized interface defined in `src/agents/base_agent.py`.

---

## Backtesting & Research Expectations

Every backtest automatically includes:
- Performance metrics (Sortino, Profit Factor, etc.)
- Benchmark vs. **buy-and-hold** (spot move + equity curve)
- Excess return calculation
- Full trade ledger and forced risk exits

**Important**: A single profitable backtest is **not** proof of edge. Always validate across multiple regimes and out-of-sample periods.

You can run backtests via:
```bash
uv run python -m backtest.run_demo --symbols BTC/USDT,ETH/USDT --steps 80
```

---

## Web UI

A Next.js dashboard is included for viewing:
- Live agent traces and reasoning
- Backtest results
- Topology visualization
- Prompt editing (where applicable)

Run with:
```bash
cd web && npm install && npm run dev
```

---

## Project Structure

```
ai-market-maker/
├── src/                    # Core Python logic
│   ├── agents/             # Individual trading desks
│   ├── tools/              # Exchange, TA, sentiment tools
│   ├── backtest/           # Backtesting engine
│   └── api/                # FastAPI endpoints
├── web/                    # Next.js dashboard
├── openclaw/               # OpenClaw skill definitions
├── config/                 # Default policy and app config
├── docs/                   # Detailed documentation
├── tests/                  # Test suite
└── .env.example
```

## 🦀 OpenClaw Integration

This project is fully compatible with OpenClaw and includes:

### Built-in Skill Package
```
openclaw/
├── SKILL.md              # Complete skill documentation
├── manifest.json         # OpenClaw skill manifest
├── scripts/              # OpenClaw-specific runners
│   ├── claw_runner.py    # Main entry point
│   └── verify_installation.sh  # Installation checker
└── examples/             # Usage examples for Claw users
```

### One-Click Installation
```bash
# From within OpenClaw
claw install https://github.com/OlaXBT-DavisNexus/ai-market-maker
# or
claw skill install ./openclaw
```

### Agentic Workflow Design
- **7 specialized trading desks** as autonomous agents
- **LangGraph orchestration** for complex decision flows
- **Hard veto layer** (Risk Guard) for safety
- **Full traceability** and reasoning logs

### Community Features
- **Korean Claw Community tested** - following best practices
- **Ready for ClawHub submission** - fully packaged skill
- **Multi-channel support** - Telegram, Discord, Web UI

---

## Using with Nexus on BNB Chain

You can run this service as part of the OlaXBT *Nexus* stack and settle usage directly on *BNB Chain (BSC / BNB Smart Chain)*.

Fund your Nexus-connected wallet with BNB or supported stablecoins on BNB Chain, then buy credits through the Nexus interface; all metered usage is settled on BNB Chain with low fees, and can later be expanded to opBNB or Greenfield–aligned workflows.

This lets agents and trading tools consume data and actions through Nexus while keeping payments and accounting native to the BNB Chain ecosystem.

---

## 🎯 Community Recognition

**Korean Claw Community** has highlighted this project as an example of:
- ✅ Proper OpenClaw skill packaging
- ✅ Agentic architecture design
- ✅ Practical trading application
- ✅ Community-shareable content

**Get involved:**
- Try it in your OpenClaw: `claw install https://github.com/OlaXBT-DavisNexus/ai-market-maker`
- Share feedback in Korean Claw communities
- Star & share to help others discover agentic trading

---

## Contributing

We welcome contributions! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) first.

Growth is driven by issues and pull requests. See the open issues for current priorities.

---

## License

[GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.html) — see [`LICENSE`](LICENSE). If you modify this software and run it as a network service, AGPL obligations (including source offer to users) may apply; read the license carefully.

---

**Built with LangGraph • FastAPI • Next.js • TA-Lib • OpenClaw**

Ready for the Korean Claw community and beyond. 🦀
