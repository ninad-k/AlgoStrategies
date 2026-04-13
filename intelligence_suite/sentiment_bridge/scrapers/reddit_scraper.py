"""
Reddit Scraper — Fetches recent posts from crypto/stock subreddits.
Uses PRAW (Python Reddit API Wrapper).
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RedditScraper:
    def __init__(self, config: dict):
        self.config = config
        self.subreddits = config.get("subreddits", ["cryptocurrency", "Bitcoin"])
        self.post_limit = config.get("post_limit", 25)
        self.reddit = None
        self._init()

    def _init(self):
        try:
            import praw
            # Uses environment variables: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
            import os
            self.reddit = praw.Reddit(
                client_id=os.getenv("REDDIT_CLIENT_ID", ""),
                client_secret=os.getenv("REDDIT_CLIENT_SECRET", ""),
                user_agent=os.getenv("REDDIT_USER_AGENT", "intelligence-suite/1.0"),
            )
            logger.info(f"Reddit scraper initialized for r/{', r/'.join(self.subreddits)}")
        except ImportError:
            logger.warning("praw not installed. Run: pip install praw")
        except Exception as e:
            logger.warning(f"Reddit init failed: {e}")

    def fetch(self, symbol_keywords: list[str] = None) -> list[dict]:
        """
        Fetch recent posts from configured subreddits.

        Args:
            symbol_keywords: Optional keywords to filter (e.g., ["BTC", "Bitcoin"])

        Returns:
            List of dicts with title, text, score, created, subreddit
        """
        if not self.reddit:
            return []

        posts = []
        for sub_name in self.subreddits:
            try:
                subreddit = self.reddit.subreddit(sub_name)
                for post in subreddit.hot(limit=self.post_limit):
                    title = post.title
                    text = post.selftext[:500] if post.selftext else ""

                    # Filter by keywords if provided
                    if symbol_keywords:
                        combined = (title + " " + text).lower()
                        if not any(kw.lower() in combined for kw in symbol_keywords):
                            continue

                    posts.append({
                        "title": title,
                        "text": text,
                        "score": post.score,
                        "num_comments": post.num_comments,
                        "subreddit": sub_name,
                        "created": datetime.fromtimestamp(post.created_utc).isoformat(),
                        "url": post.url,
                    })
            except Exception as e:
                logger.error(f"Failed to fetch r/{sub_name}: {e}")

        return posts
