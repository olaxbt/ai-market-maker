from typing import Dict
from tools.technical_indicators import calculate_rsi
from langchain.prompts import PromptTemplate
from langchain_core.language_models.llms import BaseLLM  # Abstract LLM type


class PricePatternAgent:
    def __init__(self, llm: BaseLLM = None):
        self.llm = llm  # Placeholder; no LLM for Day 2
        self.prompt = PromptTemplate(
            input_variables=["ticker", "rsi", "price_data"],
            template="Analyze price patterns for {ticker}. RSI: {rsi}. Recent prices: {price_data}. Suggest trading implications."
        )

    def analyze(self, ticker: str, market_data: Dict) -> Dict:
        try:
            # Extract OHLCV data
            ohlcv = market_data.get("ohlcv", [])
            if not ohlcv:
                return {"ticker": ticker, "status": "error", "error": "No OHLCV data"}

            # Calculate RSI
            closes = [candle[4] for candle in ohlcv]
            rsi = calculate_rsi(closes)

            # Simulate LLM analysis (replace with real LLM later)
            analysis = f"RSI analysis for {ticker}: {rsi[-1]}" if not self.llm else self.llm(
                self.prompt.format(ticker=ticker, rsi=rsi[-1], price_data=closes[-5:]))

            return {
                "ticker": ticker,
                "rsi": rsi[-1],
                "analysis": analysis,
                "status": "success"
            }
        except Exception as e:
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            }
