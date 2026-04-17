"""
RSS Scraper — Fetches headlines from news RSS feeds.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RssScraper:
    def __init__(self, config: dict):
        self.feeds = config.get("feeds", [])

    def fetch(self, symbol_keywords: list[str] = None) -> list[dict]:
        """Fetch headlines from configured RSS feeds."""
        try:
            import feedparser
        except ImportError:
            logger.warning("feedparser not installed. Run: pip install feedparser")
            return []

        articles = []
        for feed_url in self.feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:20]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")[:300]

                    if symbol_keywords:
                        combined = (title + " " + summary).lower()
                        if not any(kw.lower() in combined for kw in symbol_keywords):
                            continue

                    published = entry.get("published", "")
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_dt = parsedate_to_datetime(published).isoformat()
                    except Exception:
                        pub_dt = datetime.now().isoformat()

                    articles.append({
                        "title": title,
                        "summary": summary,
                        "source": feed_url.split("/")[2] if "/" in feed_url else feed_url,
                        "published": pub_dt,
                        "link": entry.get("link", ""),
                    })
            except Exception as e:
                logger.error(f"RSS fetch failed for {feed_url}: {e}")

        return articles
