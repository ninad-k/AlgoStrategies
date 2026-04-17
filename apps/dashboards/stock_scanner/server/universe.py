"""
US stock universe fetcher with multi-source fallback.

Priority order:
  1. Yahoo Finance Screener  (yfinance.screen + EquityQuery — NASDAQ + NYSE)
  2. SEC EDGAR company_tickers.json  (~13 000 US-listed companies, official, free)
  3. Hardcoded curated fallback (~500 liquid US stocks across all sectors)
"""

from __future__ import annotations

import logging
import re
import time

import requests

log = logging.getLogger(__name__)

SEC_EDGAR_URL = "https://www.sec.gov/files/company_tickers.json"

_YF_PAGE_SIZE   = 250
_YF_MAX_SYMBOLS = 10_000


def _is_clean(sym) -> bool:
    """Accept only plain A-Z symbols (1-5 letters, no numbers or special chars)."""
    if not sym or not isinstance(sym, str):
        return False
    return bool(re.match(r'^[A-Z]{1,5}$', sym.strip()))


# ── Source 1 : Yahoo Finance Screener (yfinance 1.x API) ─────────────────────

def _fetch_yfinance_screener() -> list[str]:
    """
    Paginate through Yahoo Finance equity screener using yfinance.screen()
    and yfinance.EquityQuery.  Collects NASDAQ + NYSE stocks with market cap
    >= $50M (filters shells/micro-caps).
    """
    import yfinance as yf

    query = yf.EquityQuery("and", [
        yf.EquityQuery("or", [
            yf.EquityQuery("eq", ["exchange", "NMS"]),
            yf.EquityQuery("eq", ["exchange", "NYQ"]),
            yf.EquityQuery("eq", ["exchange", "NGM"]),
            yf.EquityQuery("eq", ["exchange", "NCM"]),
            yf.EquityQuery("eq", ["exchange", "ASE"]),
            yf.EquityQuery("eq", ["exchange", "PCX"]),
        ]),
        yf.EquityQuery("gt", ["intradaymarketcap", 50_000_000]),
    ])

    symbols: list[str] = []
    offset = 0

    while len(symbols) < _YF_MAX_SYMBOLS:
        try:
            result = yf.screen(
                query,
                offset=offset,
                size=_YF_PAGE_SIZE,
                sortField="intradaymarketcap",
                sortAsc=False,
            )
            quotes = result.get("quotes", [])
            total  = result.get("total", 0)
        except Exception as exc:
            log.warning("[Universe] YF screen offset=%d error: %s", offset, exc)
            break

        if not quotes:
            break

        batch = [q["symbol"] for q in quotes if _is_clean(q.get("symbol", ""))]
        symbols.extend(batch)
        log.debug("[Universe] YF screen offset=%d → %d/%d symbols", offset, len(symbols), total)

        if offset + _YF_PAGE_SIZE >= total or len(quotes) < _YF_PAGE_SIZE:
            break

        offset += _YF_PAGE_SIZE
        time.sleep(0.3)

    result_list = list(dict.fromkeys(symbols))
    log.info("[Universe] Yahoo Finance screener: %d symbols", len(result_list))
    return result_list


# ── Source 2 : SEC EDGAR ──────────────────────────────────────────────────────

def _fetch_sec_edgar() -> list[str]:
    """Fetch all US-listed company tickers from SEC EDGAR (~13 000 symbols)."""
    resp = requests.get(
        SEC_EDGAR_URL,
        timeout=30,
        headers={"User-Agent": "AlgoStrategies research@example.com"},
    )
    resp.raise_for_status()
    data    = resp.json()
    tickers = [v["ticker"].upper() for v in data.values() if v.get("ticker")]
    clean   = [t for t in tickers if _is_clean(t)]
    log.info("[Universe] SEC EDGAR: %d clean symbols", len(clean))
    return clean


# ── Source 3 : Hardcoded curated fallback (~500 liquid US stocks) ─────────────

_CURATED_FALLBACK: list[str] = [
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","TSLA","JPM",
    "V","JNJ","XOM","UNH","WMT","MA","PG","HD","LLY","CVX",
    "MRK","ABBV","PEP","KO","BAC","AVGO","COST","TMO","ACN","MCD",
    "CSCO","ABT","DHR","TXN","ADBE","NKE","NEE","PM","QCOM","T",
    "LIN","CRM","RTX","HON","MS","AMGN","LOW","BLK","INTU","SPGI",
    "CAT","GS","IBM","GE","MMM","ISRG","MDLZ","ELV","SYK","PLD",
    "AMD","INTC","MU","AMAT","LRCX","KLAC","MRVL","ON","SMCI","ORCL",
    "NOW","SNOW","PLTR","PANW","CRWD","ZS","FTNT","NET","DDOG","MDB",
    "SHOP","SQ","PYPL","SE","APP","RBLX","COIN","MSTR",
    "REGN","VRTX","GILD","BIIB","MRNA","BNTX","ALNY","BMRN",
    "WFC","C","USB","PNC","TFC","SCHW","AXP","COF","DFS",
    "CVS","CI","HUM","MOH","CNC","HCA","DXCM","INSP",
    "BKNG","ABNB","UBER","LYFT","TJX","ROST","BURL","LULU","DECK",
    "F","GM","RIVN","NIO","LI","XPEV",
    "MO","KHC","GIS","MNST","KDP","CELH","STZ",
    "OXY","COP","EOG","DVN","MPC","PSX","VLO","HAL","SLB",
    "UPS","FDX","DAL","UAL","DE","WM","EMR","ROK","ETN",
    "FCX","NEM","GOLD","ALB","SQM","NUE","STLD",
    "AMT","CCI","EQIX","DLR","PSA","EXR",
    "DUK","SO","AEP","NEE","PCG","SRE",
    "NFLX","DIS","SPOT","PINS","SNAP",
    "DKNG","HOOD","SOFI","AFRM","CELH","IONQ","PCTY","PAYC",
]

_CURATED_FALLBACK = list(dict.fromkeys(_CURATED_FALLBACK))


# ── Public interface ──────────────────────────────────────────────────────────

def get_us_stock_universe() -> list[str]:
    """
    Return a deduplicated, filtered list of US common-stock ticker symbols.

    Source priority:
      1. Yahoo Finance Screener  (yfinance.screen — NASDAQ + NYSE, market cap >= $50M)
      2. SEC EDGAR               (fallback if YF returns <100 symbols)
      3. Hardcoded curated list  (final fallback)
    """
    symbols: list[str] = []

    try:
        symbols = _fetch_yfinance_screener()
    except Exception as exc:
        log.warning("[Universe] Yahoo Finance screener failed: %s", exc)

    if len(symbols) < 100:
        log.info("[Universe] YF screener insufficient — trying SEC EDGAR")
        try:
            edgar_syms = _fetch_sec_edgar()
            symbols    = sorted(set(symbols) | set(edgar_syms))
        except Exception as exc:
            log.warning("[Universe] SEC EDGAR failed: %s", exc)

    if len(symbols) < 50:
        log.warning("[Universe] All live sources failed — using curated fallback")
        symbols = sorted(set(symbols) | set(_CURATED_FALLBACK))

    result = sorted(s for s in set(symbols) if _is_clean(s))
    log.info("[Universe] Total universe: %d symbols", len(result))
    return result
