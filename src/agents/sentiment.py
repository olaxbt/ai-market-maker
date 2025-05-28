from typing import Dict
from tools.sentiment_tools import scrape_twitter
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
                    {"role": "system",
                        "content": "You are a sentiment analyst for financial markets."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            return f"Error: {str(e)}"


class SentimentAgent:
    def __init__(self):
        self.llm = OpenAIClient(api_key=os.getenv(
            "OPENAI_API_KEY")) if os.getenv("OPENAI_API_KEY") else None
        self.prompt = PromptTemplate(
            input_variables=["ticker", "tweets"],
            template="Analyze sentiment for {ticker} based on tweets: {tweets}. Provide a sentiment score (0-100, 100=very bullish)."
        )

    def analyze(self, ticker: str) -> Dict:
        try:
            tweets = scrape_twitter(ticker, max_tweets=10)
            if self.llm:
                analysis = self.llm.generate(
                    self.prompt.format(ticker=ticker, tweets=tweets)
                )
                try:
                    score = float(analysis.split("Score: ")[1].split()[0])
                except:
                    score = 50.0
            else:
                analysis = f"Simulated sentiment for {ticker}: {tweets}"
                score = 50.0

            logger.info(f"Sentiment score for {ticker}: {score}")
            return {
                "ticker": ticker,
                "sentiment_score": score,
                "analysis": analysis,
                "status": "success"
            }
        except Exception as e:
            logger.error(f"Sentiment analysis error for {ticker}: {str(e)}")
            return {
                "ticker": ticker,
                "sentiment_score": 50.0,
                "analysis": f"Error: {str(e)}",
                "status": "error"
            }
