# AI-Market-Maker

**AI-Market-Maker** is an open-source project to simulate a cryptocurrency market-making system using AI agents. It aims to provide liquidity and optimize bid-ask spreads for crypto assets like Bitcoin (BTC) and Ethereum (ETH) on exchanges such as Binance and Coinbase. This is an early-stage project for educational purposes, built with a modular agent-based architecture.

**⚠️ Note**: This project is an experimental simulation for learning purposes.

## Goals

- Simulate crypto market making with AI agents.
- Fetch real-time crypto market data and place simulated orders.
- Support future features like arbitrage, sentiment analysis, and risk management.

## Agents

- **MarketDataAgent**: Fetches real-time price, volume, and order book data from Binance using `ccxt`.
- **OrderPlacementAgent**: Simulates bid-ask quote placement with a 0.5% spread.
- **PricePatternAgent**: Analyzes price patterns using Relative Strength Index (RSI).
- **SentimentAgent**: Simulates sentiment analysis with placeholder Twitter data.
- **LangGraph**: Orchestrates agent workflow for data collection, analysis, and order placement.

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) for dependency management
- API keys for crypto exchanges (e.g., Binance)

### Steps

```bash
git clone https://github.com/olaxbt/ai-market-maker.git
cd ai-market-maker
```

2. Install Dependencies:

```
pip install uv
uv sync
```

3. Set Up Environment Variables:  
   Copy `.env.example` to `.env` and add API keys:

```bash
cp .env.example .env
```

Example .env:

```
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
```

## Usage

Run the main script (currently a placeholder):

```
uv run src/main.py
```

which stimulate

## Project Structure

```
ai-market-maker/
├── src/
│   ├── agents/
│   │   ├── market_data.py          # Fetches exchange data
│   │   ├── order_placement.py      # Places buy/sell orders
│   │   ├── price_pattern.py        # Analyzes price patterns
│   │   ├── sentiment.py            # Analyzes sentiment
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
