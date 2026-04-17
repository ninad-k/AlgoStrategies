"""
AI-powered stock insight generator.

Uses the existing _call_ai() chain (Groq → Anthropic → OpenAI) to produce
a structured investment thesis for top-ranked scanner candidates.

Called after the main scan pipeline to enrich top picks with AI commentary.
Cache: stored in the `ai_insight` column of stock_scores (persists for 24h in SQLite).
"""

from __future__ import annotations

import json
import logging
import re
import time

from .database import get_connection, get_latest_session, update_ai_insight

log = logging.getLogger(__name__)


def _build_stock_prompt(row: dict) -> str:
    """Build a focused prompt for a single stock's investment thesis."""
    sym   = row.get("symbol", "?")
    name  = row.get("company_name") or sym
    sector = row.get("sector") or "Unknown"
    industry = row.get("industry") or "Unknown"

    mc = row.get("market_cap") or 0
    mc_str = (
        f"${mc/1e9:.1f}B" if mc >= 1e9 else
        f"${mc/1e6:.0f}M" if mc >= 1e6 else "N/A"
    )

    mb_score  = row.get("multibagger_score",  0)
    inv_score = row.get("investment_score",   0)
    sw_score  = row.get("swing_medium_score", 0)

    rg  = row.get("revenue_growth")
    gm  = row.get("gross_margin")
    de  = row.get("debt_equity")
    eps = row.get("eps_trend", "UNKNOWN")
    stage  = row.get("stage", 0)
    rsi    = row.get("rsi")
    rs_spy = row.get("rs_vs_spy", 1.0)
    vol_r  = row.get("volume_ratio", 1.0)
    insider = None

    # Try to extract from score_breakdown if available
    bd_raw = row.get("score_breakdown")
    if bd_raw and isinstance(bd_raw, str):
        try:
            bd = json.loads(bd_raw)
            mb_bd = bd.get("multibagger", {})
            insider_entry = mb_bd.get("Insider Activity", {})
            insider = insider_entry.get("val")
        except Exception:
            pass

    flags_raw = row.get("red_flags")
    flags = []
    if flags_raw and isinstance(flags_raw, str):
        try:
            flags = json.loads(flags_raw)
        except Exception:
            pass

    prompt = f"""You are a senior equity research analyst specializing in growth stocks and multibagger opportunities. Analyze this US-listed stock and provide a concise, data-driven investment thesis.

## Stock Profile
- Symbol: {sym} — {name}
- Sector: {sector} | Industry: {industry}
- Market Cap: {mc_str}

## Scanner Scores (0-100)
- Multibagger Score: {mb_score:.0f}/100
- Investment Score: {inv_score:.0f}/100
- Swing 2-3 Week Score: {sw_score:.0f}/100

## Key Metrics
- Revenue Growth YoY: {f'{rg:.1f}%' if rg is not None else 'N/A'}
- Gross Margin: {f'{gm:.1f}%' if gm is not None else 'N/A'}
- Debt/Equity: {f'{de:.0f}%' if de is not None else 'N/A'}
- EPS Trend: {eps}
- Stage Analysis: {'Stage ' + str(stage) if stage else 'N/A'}
- RSI: {f'{rsi:.1f}' if rsi else 'N/A'}
- Relative Strength vs SPY: {rs_spy:.2f}x
- Volume Ratio: {vol_r:.1f}x
- Insider Activity: {insider or 'N/A'}
- Red Flags: {', '.join(flags) if flags else 'None'}

---

Respond ONLY with a raw JSON object (no markdown, no explanation outside JSON):

{{
  "investment_thesis": "<2-3 sentence explanation of WHY this stock scored highly and what makes it a potential multibagger — be specific to the data above>",
  "key_catalysts": ["<catalyst 1>", "<catalyst 2>", "<catalyst 3>"],
  "main_risk": "<single most important risk to monitor>",
  "time_horizon": "<ideal holding period: e.g. 6-18 months>",
  "conviction": "HIGH" | "MEDIUM" | "LOW"
}}"""

    return prompt


def generate_ai_insight(row: dict) -> dict | None:
    """Generate AI insight for one stock. Returns dict or None on failure."""
    # Import here to avoid circular import (this module is inside scanner package,
    # parent analyzer is one level up in server/)
    try:
        import sys
        from pathlib import Path
        # Resolve parent package's analyzer
        parent = Path(__file__).parent.parent
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        from ..analyzer import _call_ai
    except Exception as exc:
        log.warning("Could not import _call_ai: %s", exc)
        return None

    try:
        prompt = _build_stock_prompt(row)
        raw = _call_ai(prompt)

        # Strip markdown fences
        raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        if start == -1 or end == 0:
            return None

        data = json.loads(raw[start:end])
        return data
    except Exception as exc:
        log.debug("AI insight failed for %s: %s", row.get("symbol"), exc)
        return None


def enrich_top_picks(session_id: int, limit: int = 50):
    """
    Generate AI insights for the top `limit` multibagger candidates
    in the given session and store them in the DB.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM stock_scores "
            "WHERE session_id = ? AND multibagger_score >= 50 AND ai_insight IS NULL "
            "ORDER BY multibagger_score DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()

    rows = [dict(r) for r in rows]
    log.info("[AI Insight] Generating insights for %d top picks", len(rows))

    for i, row in enumerate(rows):
        sym = row.get("symbol", "?")
        try:
            insight = generate_ai_insight(row)
            if insight:
                update_ai_insight(session_id, sym, json.dumps(insight))
                log.info("[AI Insight] %s ✓ (%d/%d)", sym, i + 1, len(rows))
            else:
                log.debug("[AI Insight] %s — no result", sym)
        except Exception as exc:
            log.warning("[AI Insight] %s failed: %s", sym, exc)

        # Gentle rate limiting — avoid hammering the AI provider
        time.sleep(1.5)
