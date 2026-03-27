"""Configuration and symbol mappings for the market sentiment dashboard."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Always load .env from the dashboard root, regardless of working directory
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# ── API Keys ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GROQ_API_KEY      = os.getenv("GROQ_API_KEY", "")
NEWS_API_KEY      = os.getenv("NEWS_API_KEY", "")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY", "")

# ── Server ────────────────────────────────────────────────────────────────────
HOST      = os.getenv("HOST", "0.0.0.0")
PORT      = int(os.getenv("PORT", 8000))
CACHE_TTL = int(os.getenv("CACHE_TTL", 300))  # seconds

# ── AI provider (auto-detected from which key is set) ─────────────────────────
# Priority: GROQ → ANTHROPIC → fallback
def _is_real_key(val: str) -> bool:
    return bool(val) and not val.startswith("your_")

def _detect_provider() -> str:
    if _is_real_key(GROQ_API_KEY):
        return "groq"
    if _is_real_key(ANTHROPIC_API_KEY):
        return "anthropic"
    return "none"

AI_PROVIDER = _detect_provider()

# ── Model config ──────────────────────────────────────────────────────────────
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-6")
GROQ_MODEL   = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
MAX_NEWS_ARTICLES = int(os.getenv("MAX_NEWS_ARTICLES", 10))

# ── Symbol → Yahoo Finance ticker mapping ─────────────────────────────────────
TICKER_MAP: dict[str, str] = {
    # Indian indices
    "NIFTY": "^NSEI",
    "SENSEX": "^BSESN",
    # Indian large-cap stocks
    "HDFCBANK": "HDFCBANK.NS",
    "INFY": "INFY.NS",
    # Forex majors
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "USDCHF": "USDCHF=X",
    "EURGBP": "EURGBP=X",
    "EURJPY": "EURJPY=X",
    # Crypto
    "BTC/USDT": "BTC-USD",
    "ETH/USDT": "ETH-USD",
    # US large-cap
    "AAPL": "AAPL",
    "MSFT": "MSFT",
    "GOOGL": "GOOGL",
    "AMZN": "AMZN",
    "NVDA": "NVDA",
    # Commodities
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "OIL": "CL=F",
    # Global indices / CFDs
    "US30": "^DJI",
    "US100": "^NDX",
    "DAX": "^GDAXI",
    "GE30": "^GDAXI",
}

# ── Human-readable display names ──────────────────────────────────────────────
DISPLAY_NAMES: dict[str, str] = {
    "NIFTY": "Nifty 50",
    "SENSEX": "BSE Sensex",
    "BTC/USDT": "Bitcoin",
    "ETH/USDT": "Ethereum",
    "EURUSD": "EUR/USD",
    "GBPUSD": "GBP/USD",
    "USDJPY": "USD/JPY",
    "USDCHF": "USD/CHF",
    "EURGBP": "EUR/GBP",
    "EURJPY": "EUR/JPY",
    "XAUUSD": "Gold (XAU/USD)",
    "XAGUSD": "Silver (XAG/USD)",
    "OIL": "Crude Oil (WTI)",
    "US30": "Dow Jones 30",
    "US100": "Nasdaq 100",
    "DAX": "DAX 40",
    "GE30": "DAX 40 (GE30)",
}

# ── Symbol categories (used for grouping in UI) ───────────────────────────────
SYMBOL_GROUPS: dict[str, list[str]] = {
    "Indian Indices": ["NIFTY", "SENSEX"],
    "Indian Stocks": ["INFY", "HDFCBANK"],
    "Forex": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "EURGBP", "EURJPY"],
    "Commodities": ["XAUUSD", "XAGUSD", "OIL"],
    "Global Indices": ["US30", "US100", "DAX", "GE30"],
    "Crypto": ["BTC/USDT", "ETH/USDT"],
    "US Stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA"],
}

# ── Default symbols shown on load ─────────────────────────────────────────────
DEFAULT_SYMBOLS = ["XAUUSD", "EURUSD", "US30", "US100"]

# ── News RSS sources (symbol-agnostic + symbol-specific) ─────────────────────
RSS_FEEDS_GENERAL = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
    "https://feeds.reuters.com/reuters/businessNews",
    "https://feeds.reuters.com/reuters/topNews",
    "https://www.investing.com/rss/news.rss",
    "https://www.investing.com/rss/news_25.rss",       # Stocks
]

RSS_FEEDS_FOREX = [
    "https://www.investing.com/rss/news_14.rss",       # Forex
]

RSS_FEEDS_COMMODITIES = [
    "https://www.investing.com/rss/news_11.rss",       # Commodities
]

RSS_FEEDS_CRYPTO = [
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://www.investing.com/rss/news_301.rss",      # Crypto
]

RSS_FEEDS_INDIA = [
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "https://www.moneycontrol.com/rss/marketreports.xml",
]
