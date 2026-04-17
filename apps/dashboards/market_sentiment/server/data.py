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
    RSS_FEEDS_COMMODITIES,
    RSS_FEEDS_CRYPTO,
    RSS_FEEDS_FOREX,
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

# Human-readable keywords for symbols whose ticker names don't appear in headlines
_RSS_KEYWORD_MAP: dict[str, list[str]] = {
    "XAUUSD":   ["gold", "xau"],
    "XAGUSD":   ["silver", "xag"],
    "OIL":      ["oil", "crude", "wti"],
    "USOIL":    ["oil", "crude", "wti"],
    "US30":     ["dow jones", "dow", "djia"],
    "US100":    ["nasdaq"],
    "DAX":      ["dax", "german"],
    "GE30":     ["dax", "german"],
    "UK100":    ["ftse"],
    "SP500":    ["s&p", "s&p 500"],
    "EURUSD":   ["eurusd", "eur/usd", "euro"],
    "GBPUSD":   ["gbpusd", "gbp/usd", "sterling", "pound"],
    "USDJPY":   ["usdjpy", "usd/jpy", "yen"],
    "USDCHF":   ["usdchf", "usd/chf", "swiss franc"],
    "EURGBP":   ["eurgbp", "eur/gbp"],
    "EURJPY":   ["eurjpy", "eur/jpy"],
    "NIFTY":    ["nifty", "nse", "nifty 50"],
    "SENSEX":   ["sensex", "bse", "bombay stock"],
}


def _parse_rss(url: str, symbol: str, limit: int = 5) -> list[NewsArticle]:
    articles: list[NewsArticle] = []
    try:
        feed = feedparser.parse(url, agent="Mozilla/5.0")
        sym_lower = symbol.lower().replace("/", "").replace("usdt", "")
        # Build keyword list: ticker + any human-readable aliases
        extra_kws = [k.lower() for k in _RSS_KEYWORD_MAP.get(symbol.upper(), [])]
        keywords = [sym_lower] + extra_kws

        for entry in feed.entries[:limit * 3]:
            title = _clean_html(entry.get("title", ""))
            summary = _clean_html(entry.get("summary", entry.get("description", "")))[:500]
            if not title:
                continue
            text = (title + " " + summary).lower()
            relevant = (
                any(kw in text for kw in keywords)
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
    "XAGUSD": "silver price XAG",
    "OIL": "crude oil WTI price",
    "SENSEX": "BSE Sensex India",
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
        "NIFTY", "SENSEX",
        "HDFCBANK", "INFY",
    )
    is_commodity = symbol in ("XAUUSD", "XAGUSD", "OIL", "USOIL")
    is_forex = symbol in ("EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURGBP", "EURJPY")

    if is_crypto:
        for feed_url in RSS_FEEDS_CRYPTO:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
    elif is_india:
        for feed_url in RSS_FEEDS_INDIA:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
    elif is_commodity:
        for feed_url in RSS_FEEDS_COMMODITIES:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
        for feed_url in RSS_FEEDS_GENERAL:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
    elif is_forex:
        for feed_url in RSS_FEEDS_FOREX:
            articles.extend(_parse_rss(feed_url, symbol, limit=3))
        for feed_url in RSS_FEEDS_GENERAL:
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

_FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]
# Forex Factory source page for each event
_FF_SOURCE_URL = "https://www.forexfactory.com/calendar"


def _fetch_ff_url(url: str) -> list[dict]:
    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return resp.json()


def fetch_economic_calendar() -> list[EconomicEvent]:
    """
    Pull this week's AND next week's high/medium-impact events from
    Forex Factory's public JSON endpoints. Each event links to Forex Factory
    calendar as the source. Falls back to an empty list if unavailable.
    """
    from urllib.parse import quote_plus
    raw_items: list[dict] = []

    for url in _FF_URLS:
        try:
            raw_items.extend(_fetch_ff_url(url))
        except Exception as exc:
            log.warning("Calendar fetch failed (%s): %s", url, exc)

    events: list[EconomicEvent] = []
    for item in raw_items:
        impact_raw = (item.get("impact") or "").upper()
        impact = impact_raw if impact_raw in ("HIGH", "MEDIUM", "LOW") else "LOW"
        if impact == "LOW":
            continue

        dt_str = item.get("date", "")
        dt = None
        try:
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            scheduled = dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            scheduled = dt_str

        # Skip past events — only keep today and future
        now_utc = datetime.now(timezone.utc)
        if dt is not None and dt.date() < now_utc.date():
            continue

        title = item.get("title", "Unknown Event")
        # Direct Forex Factory calendar link as canonical source
        ff_url = _FF_SOURCE_URL
        events.append(EconomicEvent(
            title=title,
            country=item.get("country", ""),
            impact=impact,
            scheduled_time=scheduled,
            forecast=item.get("forecast") or None,
            previous=item.get("previous") or None,
            url=ff_url,
        ))

    # Sort by time
    events.sort(key=lambda e: e.scheduled_time)
    return events[:30]  # cap at 30 events
