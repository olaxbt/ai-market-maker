from typing import Dict
import numpy as np
from tools.technical_indicators import calculate_technical_indicators
from langchain.prompts import PromptTemplate
import openai
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


class OpenAIClient:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a financial analyst providing trading insights."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return f"Error: {str(e)}"


class PricePatternAgent:
    def __init__(self):
        self.llm = OpenAIClient(api_key=os.getenv(
            "OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
        self.prompt = PromptTemplate(
            input_variables=["ticker", "rsi", "sma",
                             "bb_upper", "bb_lower", "bb_mid", "price_data"],
            template="Analyze price patterns for {ticker}. RSI: {rsi}. SMA: {sma}. "
                     "Bollinger Bands (Upper: {bb_upper}, Lower: {bb_lower}, Middle: {bb_mid}). "
                     "Recent prices: {price_data}. Suggest trading implications."
        )

    def analyze(self, ticker: str, market_data: Dict) -> Dict:
        try:
            ohlcv = market_data.get("ohlcv", [])
            if not ohlcv or len(ohlcv) < 15:
                logger.warning(
                    f"Insufficient OHLCV data for {ticker}: {len(ohlcv)} candles")
                return {
                    "ticker": ticker,
                    "indicators": {"rsi": "unavailable", "sma": "unavailable", "bb_upper": "unavailable",
                                   "bb_lower": "unavailable", "bb_mid": "unavailable"},
                    "analysis": "Insufficient data for technical analysis",
                    "status": "error"
                }

            closes = [candle[4]
                      for candle in ohlcv if isinstance(candle[4], (int, float))]
            logger.debug(f"Close prices for {ticker}: {closes[-5:]}")

            indicators = calculate_technical_indicators(closes)

            # Format indicator values
            formatted_indicators = {
                "rsi": f"{indicators['rsi']:.2f}" if not np.isnan(indicators['rsi']) else "unavailable",
                "sma": f"{indicators['sma']:.2f}" if not np.isnan(indicators['sma']) else "unavailable",
                "bb_upper": f"{indicators['bb_upper']:.2f}" if not np.isnan(indicators['bb_upper']) else "unavailable",
                "bb_lower": f"{indicators['bb_lower']:.2f}" if not np.isnan(indicators['bb_lower']) else "unavailable",
                "bb_mid": f"{indicators['bb_mid']:.2f}" if not np.isnan(indicators['bb_mid']) else "unavailable"
            }

            if self.llm:
                analysis = self.llm.generate(
                    self.prompt.format(
                        ticker=ticker,
                        rsi=formatted_indicators["rsi"],
                        sma=formatted_indicators["sma"],
                        bb_upper=formatted_indicators["bb_upper"],
                        bb_lower=formatted_indicators["bb_lower"],
                        bb_mid=formatted_indicators["bb_mid"],
                        price_data=closes[-5:]
                    )
                )
            else:
                analysis = (f"Technical analysis for {ticker}: RSI={formatted_indicators['rsi']}, "
                            f"SMA={formatted_indicators['sma']}, "
                            f"Bollinger Bands (Upper={formatted_indicators['bb_upper']}, "
                            f"Lower={formatted_indicators['bb_lower']}, Mid={formatted_indicators['bb_mid']})")

            return {
                "ticker": ticker,
                "indicators": formatted_indicators,
                "analysis": analysis,
                "status": "success"
            }
        except Exception as e:
            logger.error(
                f"Price pattern analysis error for {ticker}: {str(e)}")
            return {
                "ticker": ticker,
                "indicators": {"rsi": "unavailable", "sma": "unavailable", "bb_upper": "unavailable",
                               "bb_lower": "unavailable", "bb_mid": "unavailable"},
                "analysis": f"Error: {str(e)}",
                "status": "error"
            }
