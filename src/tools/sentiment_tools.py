from typing import List


def scrape_twitter(ticker: str, max_tweets: int = 10) -> List[str]:  # MOCK
    return [f"Sample tweet about {ticker} #{ticker}" for _ in range(max_tweets)]
