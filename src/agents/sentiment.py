from typing import Dict
from tools.sentiment_tools import scrape_twitter
from langchain.prompts import PromptTemplate
from langchain_core.language_models.llms import BaseLLM


class SentimentAgent:
    def __init__(self, llm: BaseLLM = None):
        self.llm = llm
        self.prompt = PromptTemplate(
            input_variables=["ticker", "tweets"],
            template="Analyze sentiment for {ticker} based on tweets: {tweets}. Provide a sentiment score (0-100, 100=very bullish)."
        )

    def analyze(self, ticker: str) -> Dict:
        try:
            # TODO: Fetch tweets
            tweets = scrape_twitter(ticker, max_tweets=10)

            # Simulate LLM analysis
            analysis = f"Simulated sentiment for {ticker}: {tweets}" if not self.llm else self.llm(
                self.prompt.format(ticker=ticker, tweets=tweets))
            sentiment_score = 50.0  # Neutral

            return {
                "ticker": ticker,
                "sentiment_score": sentiment_score,
                "analysis": analysis,
                "status": "success"
            }
        except Exception as e:
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e)
            }
