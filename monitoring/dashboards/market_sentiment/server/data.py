"""
Data fetching: price data (yfinance), news (RSS / NewsAPI),
and economic calendar (Forex Factory public feed).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests
import yfinance as yf

from .config import (
    NEWS_API_KEY,
    MAX_NEWS_ARTICLES,
    RSS_FEEDS_CRYPTO,
    RSS_FEEDS_GENERAL,
    RSS_FEEDS_INDIA,
    TICKER_MAP,
)
from .models import EconomicEvent, NewsArticle, PriceSummary

log = logging.getLogger(__name__)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if v == v else default  # NaN check
    except Exception:
        return default


def _clean_html(raw: str) -> str:
    return re.sub(r"<[^>]+>", "", raw or "").strip()


# ── Price Data ────────────────────────────────────────────────────────────────

def fetch_price(symbol: str) -> Optional[PriceSummary]:
    ticker_sym = TICKER_MAP.get(symbol, symbol)
    try:
        tk = yf.Ticker(ticker_sym)
        info = tk.fast_info

        current = _safe_float(getattr(info, "last_price", None))
        prev_close = _safe_float(getattr(info, "previous_close", None))
        if current == 0 and prev_close == 0:
            # Fall back to history
            hist = tk.history(period="2d", interval="1d")
            if hist.empty:
                log.warning("No price data for %s (%s)", symbol, ticker_sym)
                return None
            current = _safe_float(hist["Close"].iloc[-1])
            prev_close = _safe_float(hist["Close"].iloc[-2]) if len(hist) > 1 else current

        change = current - prev_close
        change_pct = (change / prev_close * 100) if prev_close else 0.0

        return PriceSummary(
            symbol=symbol,
            ticker=ticker_sym,
            display_name=symbol,
            current_price=round(current, 4),
            open_price=round(_safe_float(getattr(info, "open", current)), 4),
            day_high=round(_safe_float(getattr(info, "day_high", current)), 4),
            day_low=round(_safe_float(getattr(info, "day_low", current)), 4),
            prev_close=round(prev_close, 4),
            change=round(change, 4),
            change_pct=round(change_pct, 2),
            volume=int(_safe_float(getattr(info, "three_month_average_volume", 0))),
            week_52_high=round(_safe_float(getattr(info, "fifty_two_week_high", current)), 4),
            week_52_low=round(_safe_float(getattr(info, "fifty_two_week_low", current)), 4),
            currency=getattr(info, "currency", "USD") or "USD",
        )
    except Exception as exc:
        log.error("Price fetch error for %s: %s", symbol, exc)
        return None


def fetch_ohlcv(symbol: str, period: str = "90d", interval: str = "1d"):
    """Return a pandas DataFrame with OHLCV data."""
    ticker_sym = TICKER_MAP.get(symbol, symbol)
    try:
        tk = yf.Ticker(ticker_sym)
        df = tk.history(period=period, interval=interval)
        df.dropna(inplace=True)
        return df
    except Exception as exc:
        log.error("OHLCV fetch error for %s: %s", symbol, exc)
        return None


# ── News ──────────────────────────────────────────────────────────────────────

def _parse_rss(url: str, symbol: str, limit: int = 5) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0")
        sym_lower = symbol.lower().replace("/", "").replace("usdt", "")
        for entry in feed.entries[:limit * 3]:
            title = _clean_html(entry.get("title", ""))
            summary = _clean_html(entry.get("summary", entry.get("description", "")))[:500]
            if not title:
                continue
            # Loose relevance filter — keep if symbol keyword found or keep all for general feeds
            relevant = (
                sym_lower in title.lower()
                or sym_lower in summary.lower()
                or len(sym_lower) <= 3  # very short tickers — keep all
            )
            if not relevant:
                continue
            published = entry.get("published", entry.get("updated", ""))
            link = entry.get("link", "")
            source = feed.feed.get("title", url.split("/")[2])
            articles.append(NewsArticle(
                title=title,
                summary=summary,
                source=source,
                published=published,
                url=link,
            ))
            if len(articles) >= limit:
                break
    except Exception as exc:
        log.debug("RSS parse error (%s): %s", url, exc)
    return articles


_NEWSAPI_QUERY_MAP = {
    "XAUUSD": "gold price XAU",
    "US30": "Dow Jones index",
    "US100": "Nasdaq 100 index",
    "DAX": "DAX German stock index",
    "GE30": "DAX German stock index",
}

def _fetch_newsapi(symbol: str, limit: int = 5) -> list[NewsArticle]:
    if not NEWS_API_KEY:
        return []
    query = _NEWSAPI_QUERY_MAP.get(symbol, symbol.replace("/USDT", "").replace("/", " "))
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": query,
        "sortBy": "publishedAt",
        "pageSize": limit,
        "language": "en",
        "apiKey": NEWS_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        articles = []
        for a in data.get("articles", []):
            articles.append(NewsArticle(
                title=a.get("title", ""),
                summary=(a.get("description") or a.get("content") or "")[:500],
                source=a.get("source", {}).get("name", "NewsAPI"),
                published=a.get("publishedAt", ""),
                url=a.get("url", ""),
            ))
        return articles
    except Exception as exc:
        log.debug("NewsAPI error for %s: %s", symbol, exc)
        return []


def _yahoo_rss_for_ticker(ticker: str) -> str:
    return f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"


def fetch_news(symbol: str) -> list[NewsArticle]:
    """Aggregate news from multiple sources for a given symbol."""
    articles: list[NewsArticle] = []
    ticker = TICKER_MAP.get(symbol, symbol)

    # 1. Yahoo Finance RSS for the specific ticker
    articles.extend(_parse_rss(_yahoo_rss_for_ticker(ticker), symbol, limit=5))

    # 2. NewsAPI (if key provided)
    if NEWS_API_KEY:
        articles.extend(_fetch_newsapi(symbol, limit=5))

    # 3. Category-specific RSS
    is_crypto = "/" in symbol or symbol in ("BTC", "ETH", "SOL")
    is_india = symbol in (
        "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK",
    )
    is_commodity = symbol in ("XAUUSD", "XAGUSD", "OIL", "USOIL")
    is_global_index = symbol in ("US30", "US100", "DAX", "GE30", "UK100", "SP500")

    if is_crypto:
        for feed_url in RSS_FEEDS_CRYPTO:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
    elif is_india:
        for feed_url in RSS_FEEDS_INDIA:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
    else:
        for feed_url in RSS_FEEDS_GENERAL:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))

    # Deduplicate by title
    seen: set[str] = set()
    unique: list[NewsArticle] = []
    for a in articles:
        key = a.title[:80].lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique[:MAX_NEWS_ARTICLES]


# ── Economic Calendar ─────────────────────────────────────────────────────────

_FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

def fetch_economic_calendar() -> list[EconomicEvent]:
    """
    Pull this week's high/medium-impact events from Forex Factory's
    public JSON endpoint. Falls back to an empty list if unavailable.
    """
    events: list[EconomicEvent] = []
    try:
        resp = requests.get(_FF_CALENDAR_URL, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        data = resp.json()
        for item in data:
            impact_raw = (item.get("impact") or "").upper()
            impact = impact_raw if impact_raw in ("HIGH", "MEDIUM", "LOW") else "LOW"
            # Only include HIGH and MEDIUM impact
            if impact == "LOW":
                continue
            # Parse datetime
            dt_str = item.get("date", "")
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
                scheduled = dt.strftime("%Y-%m-%d %H:%M UTC")
            except Exception:
                scheduled = dt_str

            title = item.get("title", "Unknown Event")
            from urllib.parse import quote_plus
            search_url = f"https://news.google.com/search?q={quote_plus(title)}"
            events.append(EconomicEvent(
                title=title,
                country=item.get("country", ""),
                impact=impact,
                scheduled_time=scheduled,
                forecast=item.get("forecast") or None,
                previous=item.get("previous") or None,
                url=search_url,
            ))
    except Exception as exc:
        log.warning("Economic calendar fetch failed: %s", exc)

    # Sort by time
    events.sort(key=lambda e: e.scheduled_time)
    return events[:30]  # cap at 30 events
