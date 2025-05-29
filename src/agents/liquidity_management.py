from typing import Dict
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class LiquidityManagementAgent:
    def analyze(self, market_data: Dict) -> Dict:
        try:
            results = {}
            for ticker, data in market_data.items():
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                if not bids or not asks:
                    continue

                bid_price = bids[0][0]
                ask_price = asks[0][0]
                spread = (ask_price - bid_price) / bid_price
                depth = sum(bid[1] for bid in bids) + sum(ask[1]
                                                          for ask in asks)

                # Adjust spread if too wide
                target_spread = 0.01  # 1%
                if spread > target_spread:
                    new_bid = bid_price * 1.005
                    new_ask = ask_price * 0.995
                else:
                    new_bid, new_ask = bid_price, ask_price

                results[ticker] = {
                    "bid": new_bid, "ask": new_ask, "spread": spread, "depth": depth}
                logger.info(
                    f"Liquidity {ticker}: Spread={spread:.4f}, Depth={depth:.2f}")

            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Liquidity error: {str(e)}")
            return {"status": "error", "analysis": str(e)}
