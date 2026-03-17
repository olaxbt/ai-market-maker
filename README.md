# AI Crypto Market Maker

**AI-Market-Maker** is an open-source, multi-agent trading stack for building fund-style workflows: research → signals → proposal → risk veto → execution. The edge is **separation of concerns** (specialist desks), **governance** (risk can halt execution), and **traceability** (personas + structured reasoning so decisions are explainable and auditable).

## Goals

- **Trading Mode (now)**: Fetch real-time market data, generate signals, and place testnet trades gated by Risk Guard.
- **Platform direction**: Treat agents as desks with clear contracts, reasoning logs, and measurable KPIs.
- Support future features like arbitrage, sentiment analysis, and risk management.
  Note: This project is an experimental simulation currently in development.

## Agents

- **Market Scanner Agent**: Scans for newly listed, to-be-delisted, and high-potential tokens with high-momentum price shifts.
- **Technical Analysis Agent**: Analyzes price patterns and candlestick data for actionable trading insights.
- **Sentiment Analysis Agent**: Processes KOL tweets and news to gauge market sentiment trends.
- **Statistical Arbitrage Agent**: Calculates correlations and hedge ratios to identify token pairs for arbitrage and hedging.
- **Quantitative Analysis Agent**: Generates trading signals by evaluating momentum and market trends.
- **Valuation Agent**: Assesses token value by benchmarking against similar category assets.
- **Liquidity Agent**: Evaluates circulating supply and on-chain liquidity for efficient trades.
- **Risk Management Agent**: Optimizes TP/SL and position limits using reinforcement learning on volatility.
- **Portfolio Management Agent**: Manages portfolio and balance for optimized order placement across DEX and CEX venues.
- **Risk Guard (Veto Layer)**: Final approval gate that can **VETO** execution proposals before any order placement.

## Why this repo is different

- **Standard interfaces**: Agents can follow a unified SOP contract (**Input → Process → Output → Feedback**) via `src/agents/base_agent.py`.
- **Governance (Veto Power)**: `Risk Guard` is a governance layer with **final say** to stop unsafe execution.
- **Personas included**: See `docs/personas/` for the 9 agent persona definitions.

## Hedge-fund style workflow (current)

The default pipeline is structured like a small fund:

- **Research desks**: Market Scan / Technical / Sentiment / Valuation
- **Alpha desks**: Quant / Stat-Arb
- **Risk desks**: Risk Management + **Risk Guard (veto)**
- **PM desk**: Portfolio proposal (capital allocation + actions)
- **Execution**: Only runs when Risk Guard returns **APPROVED**

![flow_diagram](https://github.com/user-attachments/assets/b07dc7b2-e482-416a-b684-7bc40cced45c)

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- pre-commit (recommended for contributors)
- Binance Testnet API keys (for paper trading, optional)
- OpenAI API key (for GPT-4o, optional)
- Twitter/X API bearer token (for sentiment, optional)
- TA-Lib C library (`libta-lib`) for technical indicators

### Steps

- **Clone the Repository**:

```bash
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
```

- Install Dependencies:

```
pip install uv
uv sync
```

- (Recommended) Install dev tools + git hooks:

```bash
uv sync --extra dev
uv run pre-commit install
```

- Install TA-Lib
  TA-Lib requires the C library (libta-lib) to be installed before you can install the Python wrapper. For easier installation, it is recommended to use Conda:

```
conda install -c conda-forge ta-lib
```

You can also use UV to add TA-Lib:
If you encounter any issues during the installation of TA-Lib, please refer to the [TA-Lib](https://github.com/TA-Lib/ta-lib-python) GitHub repository for assistance.

```
uv add ta-lib
```

- Set Up Environment Variables:  
   Copy `.env.example` to `.env` and add API keys:

```bash
cp .env.example .env
```

Example .env:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
OPENAI_API_KEY=your_openai_api_key
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
```

## Usage

Run the main script (**Trading Mode**, Binance testnet). The workflow generates a **portfolio proposal**, runs it through **Risk Guard**, and executes only if **APPROVED**:

```
uv run python src/main.py --ticker BTC/USDT
```

## Project Structure

```
ai-market-maker/
├── src/
│   ├── agents/
│   │   ├── market_scan.py          # Scans market and meme coins
│   │   ├── price_pattern.py        # Analyzes price patterns
│   │   ├── sentiment.py            # Analyzes sentiment
│   │   ├── stat_arb.py             # Arbitrage with cointegration
│   │   ├── quant.py                # MACD and volume signals
│   │   ├── valuation.py            # Asset valuation
│   │   ├── risk_management.py      # Position limits, stop-losses
│   │   ├── portfolio_management.py # Allocates budget and places orders
│   │   ├── liquidity_management.py # Bid-ask spread management
│   ├── tools/
│   │   ├── api.py                  # Exchange APIs
│   │   ├── technical_indicators.py # Technical analysis
│   │   ├── sentiment_tools.py      # Sentiment utilities
│   ├── main.py                     # Main entry point
├── uv.toml                         # uv configuration
├── .env.example                    # Environment variables
├── LICENSE                         # License
├── README.md                       # Documentation
```

## Using with Nexus on BNB Chain

You can run this service as part of the OlaXBT *Nexus* stack and settle usage directly on *BNB Chain (BSC / BNB Smart Chain)*.

Fund your Nexus-connected wallet with BNB or supported stablecoins on BNB Chain, then buy credits through the Nexus interface; all metered usage is settled on BNB Chain with low fees, and can later be expanded to opBNB or Greenfield–aligned workflows.

This lets agents and trading tools consume data and actions through Nexus while keeping payments and accounting native to the BNB Chain ecosystem.

## License

MIT License. See LICENSE for details.
