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
    >= $50M (filters shells/micro-caps that yfinance can't price anyway).
    """
    import yfinance as yf

    query = yf.EquityQuery("and", [
        yf.EquityQuery("or", [
            yf.EquityQuery("eq", ["exchange", "NMS"]),   # NASDAQ Global Select
            yf.EquityQuery("eq", ["exchange", "NYQ"]),   # NYSE
            yf.EquityQuery("eq", ["exchange", "NGM"]),   # NASDAQ Global Market
            yf.EquityQuery("eq", ["exchange", "NCM"]),   # NASDAQ Capital Market
            yf.EquityQuery("eq", ["exchange", "ASE"]),   # AMEX
            yf.EquityQuery("eq", ["exchange", "PCX"]),   # NYSE Arca
        ]),
        yf.EquityQuery("gt", ["intradaymarketcap", 50_000_000]),  # >= $50M market cap
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
    """
    Fetch all US-listed company tickers from SEC EDGAR.
    Returns ~10 000-13 000 ticker symbols.
    """
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
    # ── Mega-cap / S&P top 60 ──
    "AAPL","MSFT","NVDA","AMZN","GOOGL","GOOG","META","TSLA","JPM",
    "V","JNJ","XOM","UNH","WMT","MA","PG","HD","LLY","CVX",
    "MRK","ABBV","PEP","KO","BAC","AVGO","COST","TMO","ACN","MCD",
    "CSCO","ABT","DHR","TXN","ADBE","NKE","NEE","PM","QCOM","T",
    "LIN","CRM","RTX","HON","MS","AMGN","LOW","BLK","INTU","SPGI",
    "CAT","GS","IBM","GE","MMM","ISRG","MDLZ","ELV","SYK","PLD",
    # ── Tech / Semiconductors ──
    "AMD","INTC","MU","AMAT","LRCX","KLAC","MRVL","ON","QRVO","SWKS",
    "TER","MPWR","WOLF","STM","SMCI","ORCL","SAP","NOW","SNOW","PLTR",
    "PANW","CRWD","ZS","FTNT","CYBR","NET","DDOG","MDB","CFLT","GTLB",
    "HUBS","VEEV","WDAY","TEAM","OKTA","ZM","DOCU","TTD","BILL",
    "SHOP","SQ","PYPL","SE","APP","RBLX","U","MSTR","COIN",
    # ── Biotech / Pharma ──
    "REGN","VRTX","GILD","BIIB","MRNA","BNTX","ALNY","BMRN","EXEL","IONS",
    "INCY","HALO","RCKT","BEAM","EDIT","NTLA","CRSP","KYMR",
    "FOLD","RARE","ACAD","PTCT","BLUE","ARWR","MRTX","KRTX","IOVA",
    "ARVN","TPTX","IMVT","DNLI","PCRX","NKTR","AGEN","CLDX",
    # ── Financials ──
    "WFC","C","USB","PNC","TFC","SCHW","AXP","COF","DFS","SYF",
    "ALLY","CBSH","WTFC","PNFP","OZK","FFIN","BOKF","HBAN","CFG",
    "KEY","RF","MTB","FITB","NTRS","STT","BK","TROW","FDS","ICE",
    "CME","CBOE","MSCI","MCO","VRSK","BR","FIS","GPN","WEX","EFX",
    # ── Healthcare ──
    "CVS","CI","HUM","MOH","CNC","HCA","THC","UHS","ACHC","ENSG",
    "LH","DGX","PGNY","TDOC","HIMS","ACCD","DOCS",
    "NXGN","QDEL","DXCM","INSP","ATRC","RXRX",
    # ── Consumer Discretionary ──
    "BKNG","ABNB","EXPE","LYFT","UBER","DASH","PTON","TJX",
    "ROST","BURL","FIVE","OLLI","DG","DLTR","GPS","PVH","RL","HBI",
    "TPR","LULU","DECK","SKX","ONON","CROX","UA","UAA","COLM",
    "F","GM","STLA","RIVN","LCID","NIO","LI","XPEV",
    # ── Consumer Staples ──
    "MO","BTI","KHC","GIS","K","SJM","CAG","CPB","HRL",
    "MNST","KDP","CELH","FIZZ","SAM","STZ","TAP",
    # ── Energy ──
    "OXY","COP","EOG","PXD","DVN","FANG","MPC","PSX","VLO","HES",
    "HAL","SLB","BKR","NOV","HP","RIG","PBR","BP",
    "CTRA","MTDR","PR","CHRD","SM","SWN","RRC","CNX",
    # ── Industrials ──
    "UPS","FDX","DAL","UAL","AAL","LUV","JBLU","ALK",
    "DE","CNH","AGCO","TTC","WM","RSG","CLH",
    "EMR","ROK","ETN","FAST","WSO","GWW","MSM","AIT",
    # ── Materials ──
    "FCX","NEM","GOLD","AEM","KGC","WPM","AGI","PAAS","HL","CDE",
    "ALB","SQM","PLL","LAC","MP","X","CLF",
    "NUE","STLD","CMC","RS","ATI","HWM","ARNC",
    # ── Real Estate ──
    "AMT","CCI","EQIX","DLR","SBAC","PSA","EXR","CUBE","NSA",
    "VTR","WELL","OHI","STAG","IIPR",
    # ── Utilities ──
    "DUK","SO","AEP","EXC","PCG","PEG","XEL","ES","ETR",
    "PPL","CNP","AES","NI","WEC","DTE","CMS","SRE",
    # ── Communication Services ──
    "NFLX","DIS","WBD","PARA","FOXA","FOX","SIRI","SPOT","PINS","SNAP",
    "MTCH","ZG","ANGI","TRIP",
    # ── Small/Mid growth names often scanned ──
    "DKNG","HOOD","SOFI","AFRM","UPST","LMND",
    "ROOT","PRU","AFL","LNC","PFG","EQH",
    "IONQ","QUBT","RGTI","QTWO","CFLT","SMAR","PCTY","PAYC",
]

_CURATED_FALLBACK = list(dict.fromkeys(_CURATED_FALLBACK))


# ── Public interface ──────────────────────────────────────────────────────────

def get_us_stock_universe() -> list[str]:
    """
    Return a deduplicated, filtered list of US common-stock ticker symbols.

    Source priority:
      1. Yahoo Finance Screener  (yfinance.screen — NASDAQ + NYSE, market cap >= $50M)
      2. SEC EDGAR               (fallback if YF returns <100 symbols)
      3. Hardcoded curated list  (final fallback, ~500 liquid US stocks)
    """
    symbols: list[str] = []

    # ── 1. Yahoo Finance Screener ─────────────────────────────────────────────
    try:
        symbols = _fetch_yfinance_screener()
    except Exception as exc:
        log.warning("[Universe] Yahoo Finance screener failed: %s", exc)

    # ── 2. SEC EDGAR ──────────────────────────────────────────────────────────
    if len(symbols) < 100:
        log.info("[Universe] YF screener insufficient — trying SEC EDGAR")
        try:
            edgar_syms = _fetch_sec_edgar()
            combined   = set(symbols) | set(edgar_syms)
            symbols    = sorted(combined)
        except Exception as exc:
            log.warning("[Universe] SEC EDGAR failed: %s", exc)

    # ── 3. Hardcoded curated fallback ─────────────────────────────────────────
    if len(symbols) < 50:
        log.warning("[Universe] All live sources failed — using curated fallback (%d symbols)",
                    len(_CURATED_FALLBACK))
        combined = set(symbols) | set(_CURATED_FALLBACK)
        symbols  = sorted(combined)

    result = sorted(s for s in set(symbols) if _is_clean(s))
    log.info("[Universe] Total universe: %d symbols", len(result))
    return result
