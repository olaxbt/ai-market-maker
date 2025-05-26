from typing import Dict, Optional


class OrderPlacementAgent:
    def __init__(self, exchange: str):
        self.exchange = exchange

    def place_order(self, ticker: str, market_data: Dict, spread: float = 0.005) -> Dict:
        try:
            best_bid = market_data["bids"][0][0] if market_data["bids"] else None
            best_ask = market_data["asks"][0][0] if market_data["asks"] else None

            if not best_bid or not best_ask:
                return {"ticker": ticker, "status": "error", "error": "Invalid market data"}

            # Calculate mid-price and set bid/ask with spread
            mid_price = (best_bid + best_ask) / 2
            bid = mid_price * (1 - spread / 2)
            ask = mid_price * (1 + spread / 2)

            # Simulate order placement
            return {
                "ticker": ticker,
                "bid": bid,
                "ask": ask,
                "mid_price": mid_price,
                "status": "success",
                "message": f"Simulated order: Buy at {bid}, Sell at {ask}"
            }
        except Exception as e:
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            }
