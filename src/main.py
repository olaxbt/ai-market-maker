from dotenv import load_dotenv
import os
from langgraph.graph import StateGraph, END
from typing import TypedDict, Dict
from typing_extensions import Annotated
from langgraph.channels.last_value import LastValue
from agents.market_data import MarketDataAgent
from agents.order_placement import OrderPlacementAgent
from agents.price_pattern import PricePatternAgent
from agents.sentiment import SentimentAgent

# Define state with Annotated types for explicit update behavior
class MarketMakerState(TypedDict):
    ticker: Annotated[str, LastValue]  # Read-only input, single value
    market_data: Annotated[Dict, LastValue]  # Updated by fetch_market_data
    pattern_analysis: Annotated[Dict, LastValue]  # Updated by price_pattern
    sentiment_analysis: Annotated[Dict, LastValue]  # Updated by sentiment
    order_result: Annotated[Dict, LastValue]  # Updated by order_placement

def fetch_market_data_node(state: MarketMakerState) -> MarketMakerState:
    agent = MarketDataAgent(exchange="binance")
    return {"market_data": agent.fetch_data(state["ticker"])}

def price_pattern_node(state: MarketMakerState) -> MarketMakerState:
    agent = PricePatternAgent()
    return {"pattern_analysis": agent.analyze(state["ticker"], state["market_data"])}

def sentiment_node(state: MarketMakerState) -> MarketMakerState:
    agent = SentimentAgent()
    return {"sentiment_analysis": agent.analyze(state["ticker"])}

def order_placement_node(state: MarketMakerState) -> MarketMakerState:
    agent = OrderPlacementAgent(exchange="binance")
    return {"order_result": agent.place_order(state["ticker"], state["market_data"])}

def main():
    load_dotenv()

    print("AI-Market-Maker: Starting crypto market-making simulation...")

    # Setup LangGraph workflow
    workflow = StateGraph(MarketMakerState)
    
    # Add nodes
    workflow.add_node("fetch_market_data", fetch_market_data_node)
    workflow.add_node("price_pattern", price_pattern_node)
    workflow.add_node("sentiment", sentiment_node)
    workflow.add_node("order_placement", order_placement_node)
    
    # Define edges
    workflow.add_edge("fetch_market_data", "price_pattern")
    workflow.add_edge("fetch_market_data", "sentiment")
    workflow.add_edge("price_pattern", "order_placement")
    workflow.add_edge("sentiment", "order_placement")
    workflow.add_edge("order_placement", END)
    
    # Set entry point
    workflow.set_entry_point("fetch_market_data")
    
    # Compile and run
    app = workflow.compile()
    result = app.invoke({"ticker": "BTC/USDT"})
    
    print("Cycle complete. Results:")
    print(f"Market Data: {result['market_data']}")
    print(f"Price Pattern: {result['pattern_analysis']}")
    print(f"Sentiment: {result['sentiment_analysis']}")
    print(f"Order Result: {result['order_result']}")

if __name__ == "__main__":
    main()