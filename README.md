# AI Crypto Market Maker

**AI-Market-Maker** is an open-source project to simulate a cryptocurrency market-making system using AI agents. It aims to provide liquidity and optimize bid-ask spreads for crypto assets like Bitcoin (BTC) and Ethereum (ETH) on exchanges such as Binance and Coinbase. This is an early-stage project for educational purposes, built with a modular agent-based architecture.

## Goals

- Simulate crypto market making with AI agents.
- Fetch real-time crypto market data and place simulated orders.
- Support future features like arbitrage, sentiment analysis, and risk management.
  Note: This project is an experimental simulation currently in development.

## Agents

- **Market Scanning**: Fetches OHLCV and order book data for specified tickers and scans meme coins.
- **Technical Analysis**: Uses **TA-Lib** to analyze price patterns.
- **Sentiment Analysis**: Analyzes sentiment for tickers via Twitter.
- **Statistical Arbitrage**: Identifies arbitrage opportunities.
- **Quantitative Analysis**: Uses OpenAI `gpt-4o` for signal generation.
- **Valuation and Liquidity**: Assesses asset valuation and liquidity.
- **Risk Management**: Computes position sizes and stop-loss levels based on volatility and valuation.
- **Portfolio Management**: Allocates budget across assets and places buy/sell orders
- **Sequential Workflow**: Processes nodes sequentially to avoid state conflicts.

![flow_diagram](https://github.com/user-attachments/assets/b07dc7b2-e482-416a-b684-7bc40cced45c)

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

## License

MIT License. See LICENSE for details.
