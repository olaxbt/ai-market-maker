import os
import argparse
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from typing import Dict, TypedDict
from typing_extensions import Annotated
from langgraph.channels.last_value import LastValue
from agents.market_data import MarketDataAgent
from agents.order_placement import OrderPlacementAgent
from agents.price_pattern import PricePatternAgent
from agents.sentiment import SentimentAgent
from agents.stat_arb import StatArbAgent
import logging

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class MarketMakerState(TypedDict):
    ticker: Annotated[str, LastValue]
    market_data: Annotated[Dict, LastValue]
    pattern_analysis: Annotated[Dict, LastValue]
    sentiment_analysis: Annotated[Dict, LastValue]
    arb_analysis: Annotated[Dict, LastValue]
    order_result: Annotated[Dict, LastValue]


def fetch_market_data_node(state: MarketMakerState) -> Dict:
    agent = MarketDataAgent(exchange="binance", testnet=True)
    data = agent.fetch_data(state["ticker"])
    logger.info(f"Fetched market data for {state['ticker']}: {data['status']}")
    return {"market_data": data}


def price_pattern_node(state: MarketMakerState) -> Dict:
    agent = PricePatternAgent()
    analysis = agent.analyze(state["ticker"], state["market_data"])
    logger.info(
        f"Price pattern analysis for {state['ticker']}: RSI={analysis.get('rsi')}")
    return {"pattern_analysis": analysis}


def sentiment_node(state: MarketMakerState) -> Dict:
    agent = SentimentAgent()
    analysis = agent.analyze(state["ticker"])
    logger.info(
        f"Sentiment analysis for {state['ticker']}: Score={analysis.get('sentiment_score')}")
    return {"sentiment_analysis": analysis}


def stat_arb_node(state: MarketMakerState) -> Dict:
    agent = StatArbAgent(exchange="binance")
    analysis = agent.analyze(state["ticker"], "ETH/USDT")
    logger.info(
        f"Arbitrage analysis for {state['ticker']}, ETH/USDT: Signal={analysis.get('signal')}")
    return {"arb_analysis": analysis}


def order_placement_node(state: MarketMakerState) -> Dict:
    agent = OrderPlacementAgent(exchange="binance", testnet=True)
    quantity = 0.001
    if state["pattern_analysis"].get("rsi", "50.00") < "30.00":
        quantity *= 1.5
    if state["sentiment_analysis"].get("sentiment_score", 50) > 75:
        quantity *= 1.2
    if state["arb_analysis"].get("signal", "").startswith("Buy"):
        quantity *= 1.3
    result = agent.place_order(
        state["ticker"], state["market_data"], quantity=quantity)
    logger.info(f"Order result for {state['ticker']}: {result['message']}")
    return {"order_result": result}


def main():
    parser = argparse.ArgumentParser(description="AI-Market-Maker Simulation")
    parser.add_argument("--ticker", default="BTC/USDT",
                        help="Trading pair (e.g., BTC/USDT)")
    args = parser.parse_args()

    logger.info("AI-Market-Maker: Starting simulation...")

    workflow = StateGraph(MarketMakerState)
    workflow.add_node("fetch_data", fetch_market_data_node)
    workflow.add_node("price_pattern", price_pattern_node)
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("stat_arb", stat_arb_node)
    workflow.add_node("order_placement", order_placement_node)
    workflow.add_edge("fetch_data", "price_pattern")
    workflow.add_edge("fetch_data", "sentiment")
    workflow.add_edge("fetch_data", "stat_arb")
    workflow.add_edge("price_pattern", "order_placement")
    workflow.add_edge("sentiment", "order_placement")
    workflow.add_edge("stat_arb", "order_placement")
    workflow.add_edge("order_placement", END)
    workflow.set_entry_point("fetch_data")

    app = workflow.compile()
    result = app.invoke({"ticker": args.ticker})

    logger.info("Cycle complete. Results:")
    logger.info(f"Market Data: {result['market_data']}")
    logger.info(f"Price Pattern: {result['pattern_analysis']}")
    logger.info(f"Sentiment: {result['sentiment_analysis']}")
    logger.info(f"Arbitrage: {result['arb_analysis']}")
    logger.info(f"Order Result: {result['order_result']}")


if __name__ == "__main__":
    main()
