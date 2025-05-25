# AI-Market-Maker

**AI-Market-Maker** is an open-source project to simulate a cryptocurrency market-making system using AI agents. It aims to provide liquidity and optimize bid-ask spreads for crypto assets like Bitcoin (BTC) and Ethereum (ETH) on exchanges such as Binance and Coinbase. This is an early-stage project for educational purposes, built with a modular agent-based architecture.

**⚠️ Disclaimer**: This is for **educational use only**. Not intended for real-world trading.

## Goals

- Simulate crypto market making with AI agents.
- Fetch real-time crypto market data and place simulated orders.
- Support future features like arbitrage, sentiment analysis, and risk management.

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

## License

MIT License. See LICENSE for details.
