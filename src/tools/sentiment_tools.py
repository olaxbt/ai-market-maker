from typing import List
import tweepy
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")
logger = logging.getLogger(__name__)


def scrape_twitter(ticker: str, max_tweets: int = 10) -> List[str]:
    try:
        if not os.getenv("TWITTER_BEARER_TOKEN"):
            logger.warning(
                f"No Twitter API credentials for {ticker}, using placeholder")
            return [f"Sample tweet about {ticker} #{ticker}" for _ in range(max_tweets)]

        client = tweepy.Client(bearer_token=os.getenv("TWITTER_BEARER_TOKEN"))
        query = f"#{ticker.replace('/', '')} -is:retweet lang:en"
        tweets = client.search_recent_tweets(
            query=query, max_results=max_tweets)

        if not tweets.data:
            logger.info(f"No tweets found for {ticker}")
            return ["No recent tweets found"]

        result = [tweet.text for tweet in tweets.data]
        logger.info(f"Fetched {len(result)} tweets for {ticker}")
        return result
    except Exception as e:
        logger.error(f"Twitter scraping error for {ticker}: {str(e)}")
        return [f"Error fetching tweets: {str(e)}"]
