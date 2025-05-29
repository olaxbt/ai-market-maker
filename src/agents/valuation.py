from typing import Dict, List
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class ValuationAgent:
    def analyze(self, market_data: Dict, meme_coins: List[Dict]) -> Dict:
        try:
            results = {}
            for coin in meme_coins:
                ticker = coin["symbol"]
                volume = coin["volume"]
                market_cap = coin["market_cap"]

                # Volume-to-market-cap ratio
                vol_mcap_ratio = volume / market_cap if market_cap > 0 else 0
                valuation = "undervalued" if vol_mcap_ratio > 0.1 else "overvalued" if vol_mcap_ratio < 0.05 else "fair"

                results[ticker] = {"valuation": valuation,
                                   "vol_mcap_ratio": vol_mcap_ratio}
                logger.info(
                    f"Valuation {ticker}: {valuation}, Ratio={vol_mcap_ratio:.4f}")

            return {"status": "success", "analysis": results}
        except Exception as e:
            logger.error(f"Valuation error: {str(e)}")
            return {"status": "error", "analysis": str(e)}
