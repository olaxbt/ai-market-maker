import os
import argparse
from typing import Dict, Any
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
import ccxt
from agents.market_scan import MarketScanAgent
from agents.price_pattern import PricePatternAgent
from agents.sentiment import SentimentAgent
from agents.stat_arb import StatArbAgent
from agents.quant import QuantAgent
from agents.valuation import ValuationAgent
from agents.risk_management import RiskManagementAgent
from agents.portfolio_management import PortfolioManagementAgent
from agents.liquidity_management import LiquidityManagementAgent
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)

load_dotenv()

# Define state as a dictionary
State = Dict[str, Any]


def market_scan(state: State) -> State:
    logger.debug(f"Running market_scan node with state: {state}")
    ticker = state.get("ticker")
    if not ticker or not isinstance(ticker, str):
        logger.error("Invalid or missing ticker, using default BTC/USDT")
        ticker = "BTC/USDT"

    agent = MarketScanAgent(testnet=True)
    data = state.get("market_data", {})
    try:
        data[ticker] = agent.fetch_data(ticker)
        logger.debug(f"Fetched data for {ticker}: {data[ticker]}")
    except Exception as e:
        logger.error(f"Failed to fetch data for {ticker}: {str(e)}")
        data[ticker] = {"status": "error", "error": str(e)}

    meme_coins = agent.scan_meme_coins()
    for coin in meme_coins[:2]:
        if coin["symbol"] in agent.exchange.markets:
            try:
                data[coin["symbol"]] = agent.fetch_data(coin["symbol"])
            except Exception as e:
                logger.error(
                    f"Failed to fetch data for {coin['symbol']}: {str(e)}")
                data[coin["symbol"]] = {"status": "error", "error": str(e)}

    result = {
        **state,
        "ticker": ticker,
        "market_data": data,
        "market_scan": meme_coins
    }
    logger.debug(f"market_scan output: {result}")
    return result


def price_pattern(state: State) -> State:
    logger.debug(f"Running price_pattern node with state: {state}")
    ticker = state.get("ticker", "BTC/USDT")
    market_data = state.get("market_data", {})
    agent = PricePatternAgent()
    result = {
        **state,
        "pattern_analysis": agent.analyze(ticker, market_data)
    }
    logger.debug(f"price_pattern output: {result}")
    return result


def sentiment(state: State) -> State:
    logger.debug(f"Running sentiment node with state: {state}")
    ticker = state.get("ticker", "BTC/USDT")
    agent = SentimentAgent()
    result = {
        **state,
        "sentiment_analysis": agent.analyze(ticker)
    }
    logger.debug(f"sentiment output: {result}")
    return result


def stat_arb(state: State) -> State:
    logger.debug(f"Running stat_arb node with state: {state}")
    market_data = state.get("market_data", {})
    market_scan = state.get("market_scan", [])
    agent = StatArbAgent()
    result = {
        **state,
        "arb_analysis": agent.analyze(market_data, market_scan)
    }
    logger.debug(f"stat_arb output: {result}")
    return result


def quant(state: State) -> State:
    logger.debug(f"Running quant node with state: {state}")
    market_data = state.get("market_data", {})
    agent = QuantAgent()
    result = {
        **state,
        "quant_analysis": agent.analyze(market_data)
    }
    logger.debug(f"quant output: {result}")
    return result


def valuation(state: State) -> State:
    logger.debug(f"Running valuation node with state: {state}")
    market_data = state.get("market_data", {})
    market_scan = state.get("market_scan", [])
    agent = ValuationAgent()
    result = {
        **state,
        "valuation": agent.analyze(market_data, market_scan)
    }
    logger.debug(f"valuation output: {result}")
    return result


def liquidity(state: State) -> State:
    logger.debug(f"Running liquidity node with state: {state}")
    market_data = state.get("market_data", {})
    agent = LiquidityManagementAgent()
    result = {
        **state,
        "liquidity": agent.analyze(market_data)
    }
    logger.debug(f"liquidity output: {result}")
    return result


def risk(state: State) -> State:
    logger.debug(f"Running risk node with state: {state}")
    market_data = state.get("market_data", {})
    valuation = state.get("valuation", {})
    agent = RiskManagementAgent()
    result = {
        **state,
        "risk": agent.analyze(market_data, valuation)
    }
    logger.debug(f"risk output: {result}")
    return result


def portfolio(state: State) -> State:
    logger.debug(f"Running portfolio node with state: {state}")
    agent = PortfolioManagementAgent(testnet=True)
    result = {
        **state,
        "portfolio": agent.analyze(
            state.get("ticker", "BTC/USDT"),
            state.get("market_data", {}),
            state.get("pattern_analysis", {}),
            state.get("sentiment_analysis", {}),
            state.get("arb_analysis", {}),
            state.get("quant_analysis", {}),
            state.get("valuation", {}),
            state.get("risk", {}),
            state.get("liquidity", {})
        )
    }
    logger.debug(f"portfolio output: {result}")
    return result


def validate_ticker(ticker: str) -> bool:
    """Check if ticker is valid on Binance Testnet."""
    try:
        exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY"),
            "secret": os.getenv("BINANCE_API_SECRET"),
            "enableRateLimit": True
        })
        exchange.set_sandbox_mode(True)
        exchange.load_markets()
        return ticker in exchange.markets
    except Exception as e:
        logger.error(f"Error validating ticker {ticker}: {str(e)}")
        return False


def main():
    parser = argparse.ArgumentParser(description="AI Market Maker")
    parser.add_argument("--ticker", type=str,
                        default="BTC/USDT", help="Trading pair")
    args = parser.parse_args()

    # Validate ticker
    if not args.ticker or not validate_ticker(args.ticker):
        logger.error(f"Invalid ticker: {args.ticker}")
        raise ValueError(
            f"Invalid ticker: {args.ticker}. Use a valid Binance Testnet pair (e.g., BTC/USDT).")

    # Initialize state as a dictionary
    state = {
        "ticker": args.ticker,
        "market_data": {},
        "market_scan": [],
        "pattern_analysis": {},
        "sentiment_analysis": {},
        "arb_analysis": {},
        "quant_analysis": {},
        "valuation": {},
        "risk": {},
        "portfolio": {},
        "liquidity": {}
    }
    logger.debug(f"Initial state: {state}")

    workflow = StateGraph(State)
    workflow.add_node("market_scan", market_scan)
    workflow.add_node("price_pattern", price_pattern)
    workflow.add_node("sentiment", sentiment)
    workflow.add_node("stat_arb", stat_arb)
    workflow.add_node("quant", quant)
    workflow.add_node("valuation", valuation)
    workflow.add_node("liquidity", liquidity)
    workflow.add_node("risk", risk)
    workflow.add_node("portfolio", portfolio)

    # Sequential workflow
    workflow.set_entry_point("market_scan")
    workflow.add_edge("market_scan", "price_pattern")
    workflow.add_edge("price_pattern", "sentiment")
    workflow.add_edge("sentiment", "stat_arb")
    workflow.add_edge("stat_arb", "quant")
    workflow.add_edge("quant", "valuation")
    workflow.add_edge("valuation", "liquidity")
    workflow.add_edge("liquidity", "risk")
    workflow.add_edge("risk", "portfolio")
    workflow.add_edge("portfolio", END)

    app = workflow.compile()
    try:
        result = app.invoke(state)
        logger.info(f"Final state: {result}")
    except Exception as e:
        logger.error(f"Workflow error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
