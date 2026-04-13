"""
Sentiment Signal Generator — Aggregates all sentiment sources into a single signal.
"""

import logging
from datetime import datetime

from .scrapers.reddit_scraper import RedditScraper
from .scrapers.rss_scraper import RssScraper
from .scrapers.fear_greed import FearGreedIndex
from .analyzer import SentimentAnalyzer

logger = logging.getLogger(__name__)

# Map symbols to search keywords
SYMBOL_KEYWORDS = {
    "BTCUSD": ["BTC", "Bitcoin", "bitcoin"],
    "ETHUSD": ["ETH", "Ethereum", "ethereum"],
    "LTCUSD": ["LTC", "Litecoin", "litecoin"],
    "XRPUSD": ["XRP", "Ripple", "ripple"],
    "SOLUSD": ["SOL", "Solana", "solana"],
}


class SentimentSignalGenerator:
    def __init__(self, config: dict):
        self.config = config
        sentiment_cfg = config.get("sentiment", {})

        self.reddit = None
        self.rss = None
        self.fear_greed = None
        self.analyzer = SentimentAnalyzer(config)

        if sentiment_cfg.get("sources", {}).get("reddit", {}).get("enabled"):
            self.reddit = RedditScraper(sentiment_cfg["sources"]["reddit"])
        if sentiment_cfg.get("sources", {}).get("rss", {}).get("enabled"):
            self.rss = RssScraper(sentiment_cfg["sources"]["rss"])
        if sentiment_cfg.get("sources", {}).get("fear_greed", {}).get("enabled"):
            self.fear_greed = FearGreedIndex(sentiment_cfg["sources"]["fear_greed"])

        self.cache = {}  # symbol -> {score, timestamp, sources}

    def generate_signal(self, symbol: str) -> dict:
        """
        Generate aggregate sentiment signal for a symbol.

        Returns:
            dict with:
                score: float -1.0 to +1.0
                sources: dict of per-source scores
                headlines: list of top headlines
                fear_greed: dict
        """
        keywords = SYMBOL_KEYWORDS.get(symbol, [symbol])
        headlines = []
        sources = {}

        # Fetch from all sources
        if self.reddit:
            posts = self.reddit.fetch(keywords)
            reddit_headlines = [p["title"] for p in posts]
            headlines.extend(reddit_headlines)
            if reddit_headlines:
                result = self.analyzer.analyze_headlines(reddit_headlines, symbol)
                sources["reddit"] = result.get("score", 0)

        if self.rss:
            articles = self.rss.fetch(keywords)
            rss_headlines = [a["title"] for a in articles]
            headlines.extend(rss_headlines)
            if rss_headlines:
                result = self.analyzer.analyze_headlines(rss_headlines, symbol)
                sources["rss"] = result.get("score", 0)

        fear_greed_data = {}
        if self.fear_greed:
            fear_greed_data = self.fear_greed.fetch()
            sources["fear_greed"] = fear_greed_data.get("normalized", 0)

        # Weighted aggregate
        weights = {"reddit": 0.35, "rss": 0.40, "fear_greed": 0.25}
        total_score = 0
        total_weight = 0
        for source, score in sources.items():
            w = weights.get(source, 0.33)
            total_score += score * w
            total_weight += w

        final_score = total_score / total_weight if total_weight > 0 else 0

        signal = {
            "symbol": symbol,
            "score": round(final_score, 3),
            "sources": sources,
            "headlines": headlines[:10],
            "fear_greed": fear_greed_data,
            "timestamp": datetime.now().isoformat(),
        }

        self.cache[symbol] = signal
        return signal

    def get_cached_signal(self, symbol: str) -> dict:
        """Get the last computed sentiment signal for a symbol."""
        return self.cache.get(symbol, {"symbol": symbol, "score": 0.0})
