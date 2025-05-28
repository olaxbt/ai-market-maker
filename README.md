# AI-Market-Maker

**AI-Market-Maker** is an open-source project to simulate a cryptocurrency market-making system using AI agents. It aims to provide liquidity and optimize bid-ask spreads for crypto assets like Bitcoin (BTC) and Ethereum (ETH) on exchanges such as Binance and Coinbase. This is an early-stage project for educational purposes, built with a modular agent-based architecture.

## Goals

- Simulate crypto market making with AI agents.
- Fetch real-time crypto market data and place simulated orders.
- Support future features like arbitrage, sentiment analysis, and risk management.
  Note: This project is an experimental simulation currently in development.

## Agents

- **MarketDataAgent**: Fetches real-time price, volume, and order book data via `ccxt`.
- **OrderPlacementAgent**: Places paper trades on Binance Testnet or simulates trades.
- **PricePatternAgent**: Analyzes RSI, SMA, and Bollinger Bands with OpenAI GPT-4o insights.
- **SentimentAgent**: Uses Twitter data (`tweepy`) and OpenAI GPT-4o for sentiment scores.
- **StatArbAgent**: Identifies arbitrage opportunities (e.g., BTC/USDT vs. ETH/USDT).
- **LangGraph**: Orchestrates data, analysis, and trading workflows.
- **Trade Simulation**: Logs trades to `trades.log` with position tracking.
- **CLI Support**: Run with custom tickers (e.g., `--ticker ETH/USDT`).

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
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

Run the main script (currently a placeholder):

```
uv run python src/main.py --ticker BTC/USDT
```

## Project Structure

```
ai-market-maker/
├── src/
│   ├── agents/
│   │   ├── market_data.py          # Fetches exchange data
│   │   ├── order_placement.py      # Places buy/sell orders
│   │   ├── price_pattern.py        # Analyzes price patterns
│   │   ├── sentiment.py            # Analyzes sentiment
│   │   ├── stat_arb.py             # Arbitrage
│   ├── tools/
│   │   ├── api.py                  # Exchange APIs
│   │   ├── technical_indicators.py # Technical analysis
│   │   ├── sentiment_tools.py      # Sentiment utils
│   ├── main.py                     # Main entry point
├── uv.toml                         # uv configuration
├── .env.example                    # Environment variables
├── LICENSE                         # LiCENSE
├── README.md                       # Documentation

```

## License

MIT License. See LICENSE for details.
