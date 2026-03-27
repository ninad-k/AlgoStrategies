"""
AI market analyzer — supports Groq (free) and Anthropic Claude.

Auto-detects which provider to use based on which API key is set in .env.
Priority: GROQ_API_KEY → ANTHROPIC_API_KEY → fallback neutral response.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone

from .config import AI_PROVIDER, ANTHROPIC_API_KEY, CLAUDE_MODEL, GROQ_API_KEY, GROQ_MODEL
from .models import (
    EconomicEvent,
    NewsArticle,
    PredictionDetail,
    PriceSummary,
    SymbolAnalysis,
    TechnicalLevels,
)
from .technical import format_levels_for_prompt

log = logging.getLogger(__name__)

_anthropic_client = None
_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _get_anthropic_client():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client


def _call_groq(prompt: str) -> str:
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.3,
    )
    return response.choices[0].message.content


def _call_anthropic(prompt: str) -> str:
    client = _get_anthropic_client()
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def _call_ai(prompt: str) -> str:
    """Call AI provider with fallback: Groq → Anthropic → error."""
    if AI_PROVIDER == "groq":
        try:
            return _call_groq(prompt)
        except Exception as exc:
            log.warning("Groq failed (%s), falling back to Anthropic", exc)
            if ANTHROPIC_API_KEY:
                return _call_anthropic(prompt)
            raise

    if AI_PROVIDER == "anthropic":
        return _call_anthropic(prompt)

    raise RuntimeError("No AI provider configured. Set GROQ_API_KEY or ANTHROPIC_API_KEY in .env")


# ── Prompt Builder ────────────────────────────────────────────────────────────

def _build_prompt(
    symbol: str,
    display_name: str,
    price: PriceSummary,
    technical: TechnicalLevels,
    news: list[NewsArticle],
    events: list[EconomicEvent],
) -> str:
    news_text = ""
    if news:
        items = []
        for i, a in enumerate(news[:10], 1):
            items.append(
                f"{i}. [{a.source}] {a.title}\n   {a.summary[:200]}"
            )
        news_text = "\n".join(items)
    else:
        news_text = "No recent news available."

    events_text = ""
    if events:
        relevant = [
            e for e in events
            if e.impact in ("HIGH", "MEDIUM")
        ][:8]
        if relevant:
            items = []
            for e in relevant:
                forecast = f"Forecast: {e.forecast}" if e.forecast else ""
                previous = f"Previous: {e.previous}" if e.previous else ""
                extras = " | ".join(filter(None, [forecast, previous]))
                items.append(
                    f"• [{e.impact}] {e.country} — {e.title} @ {e.scheduled_time}"
                    + (f"\n  {extras}" if extras else "")
                )
            events_text = "\n".join(items)
        else:
            events_text = "No high/medium impact events scheduled."
    else:
        events_text = "Economic calendar unavailable."

    tech_text = format_levels_for_prompt(technical, price.current_price)

    prompt = f"""You are a professional financial analyst and market strategist. Analyze the following market data for **{display_name} ({symbol})** and provide a structured market outlook.

## Current Price Data
- Symbol: {symbol} ({display_name})
- Current Price: {price.current_price} {price.currency}
- Open: {price.open_price} | High: {price.day_high} | Low: {price.day_low}
- Previous Close: {price.prev_close}
- Daily Change: {price.change:+.4f} ({price.change_pct:+.2f}%)
- 52-Week High: {price.week_52_high} | 52-Week Low: {price.week_52_low}

## Technical Analysis
{tech_text}

## Recent News & Sentiment (last 24–72 hours)
{news_text}

## Upcoming Economic Events
{events_text}

---

Based on all available data, respond with a JSON object following EXACTLY this schema (no markdown fences, raw JSON only):

{{
  "sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
  "confidence": <integer 0-100>,
  "summary": "<2-3 sentence concise market overview>",
  "key_reasons": ["<reason 1>", "<reason 2>", "<reason 3>"],
  "support_levels": [<price>, <price>, <price>],
  "resistance_levels": [<price>, <price>, <price>],
  "prediction": {{
    "direction": "UP" | "DOWN" | "SIDEWAYS",
    "timeframe": "<e.g. 1-3 days>",
    "target": <price or null>,
    "stop_loss": <price or null>,
    "confidence": <integer 0-100>
  }},
  "risks": ["<risk 1>", "<risk 2>"],
  "news_sentiment": "POSITIVE" | "NEGATIVE" | "NEUTRAL",
  "event_impact": "HIGH" | "MEDIUM" | "LOW"
}}

Important:
- support_levels and resistance_levels must be 3 price levels each, chosen from the pivot points and swing levels provided, adjusted for the current price context.
- Be specific and data-driven. Do NOT include disclaimers or generic advice.
- Respond with raw JSON only — no explanation text outside the JSON."""

    return prompt


# ── JSON Extraction ───────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict:
    """Extract the first JSON object from the model response."""
    # Strip markdown fences if present
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    # Find the outermost braces
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")
    return json.loads(text[start:end])


# ── Main Analysis Function ────────────────────────────────────────────────────

def analyze_symbol(
    symbol: str,
    display_name: str,
    group: str,
    price: PriceSummary,
    technical: TechnicalLevels,
    news: list[NewsArticle],
    events: list[EconomicEvent],
) -> SymbolAnalysis:
    """
    Call Claude to analyze a symbol and return a SymbolAnalysis object.
    Falls back to a neutral/default analysis on any error.
    """
    prompt = _build_prompt(symbol, display_name, price, technical, news, events)

    try:
        raw_text = _call_ai(prompt)
        data = _extract_json(raw_text)
    except Exception as exc:
        log.error("Claude analysis error for %s: %s", symbol, exc)
        # Fallback neutral analysis
        data = _fallback_data(technical, price)

    # Safely extract prediction sub-object
    pred_raw = data.get("prediction", {})
    prediction = PredictionDetail(
        direction=pred_raw.get("direction", "SIDEWAYS"),
        timeframe=pred_raw.get("timeframe", "1-3 days"),
        target=pred_raw.get("target"),
        stop_loss=pred_raw.get("stop_loss"),
        confidence=int(pred_raw.get("confidence", 50)),
    )

    # Merge Claude-chosen levels back into technical for the final object
    def _pick(levels_list, fallback: list[float]) -> list[float]:
        vals = [float(v) for v in (levels_list or []) if v is not None]
        return vals[:3] if len(vals) >= 3 else fallback

    merged_supports = _pick(
        data.get("support_levels"), technical.supports
    )
    merged_resistances = _pick(
        data.get("resistance_levels"), technical.resistances
    )

    enhanced_technical = TechnicalLevels(
        pivot=technical.pivot,
        supports=merged_supports,
        resistances=merged_resistances,
        swing_supports=technical.swing_supports,
        swing_resistances=technical.swing_resistances,
        rsi_14=technical.rsi_14,
        macd_signal=technical.macd_signal,
        trend_signal=technical.trend_signal,
        atr=technical.atr,
    )

    return SymbolAnalysis(
        symbol=symbol,
        display_name=display_name,
        group=group,
        price=price,
        technical=enhanced_technical,
        sentiment=data.get("sentiment", "NEUTRAL"),
        confidence=int(data.get("confidence", 50)),
        summary=data.get("summary", "Analysis unavailable."),
        key_reasons=data.get("key_reasons", []),
        prediction=prediction,
        risks=data.get("risks", []),
        news_sentiment=data.get("news_sentiment", "NEUTRAL"),
        event_impact=data.get("event_impact", "LOW"),
        news=news,
        analyzed_at=datetime.now(timezone.utc).isoformat(),
    )


def _fallback_data(technical: TechnicalLevels, price: PriceSummary) -> dict:
    """
    Rule-based analysis from pure technical data when AI is unavailable.
    No generic placeholder text — every field is derived from real numbers.
    """
    rsi = technical.rsi_14 or 50.0
    macd = technical.macd_signal or "NEUTRAL"
    trend = technical.trend_signal or "SIDEWAYS"
    chg = price.change_pct

    # ── Sentiment scoring ──────────────────────────────────────────────────────
    score = 0
    if chg > 0:          score += 1
    if chg > 1:          score += 1
    if rsi < 40:         score += 1   # oversold = bullish opportunity
    if rsi > 60:         score -= 1   # overbought = bearish pressure
    if macd == "BULLISH": score += 2
    if macd == "BEARISH": score -= 2
    if trend == "UPTREND":   score += 1
    if trend == "DOWNTREND": score -= 1

    if score >= 2:
        sentiment, direction, confidence = "BULLISH", "UP",      55 + min(score * 5, 20)
    elif score <= -2:
        sentiment, direction, confidence = "BEARISH", "DOWN",    55 + min(abs(score) * 5, 20)
    else:
        sentiment, direction, confidence = "NEUTRAL", "SIDEWAYS", 45

    # ── Key reasons from real data ─────────────────────────────────────────────
    reasons = []
    reasons.append(
        f"Price is {'up' if chg >= 0 else 'down'} {abs(chg):.2f}% "
        f"({'above' if price.current_price > price.prev_close else 'below'} previous close {price.prev_close})"
    )
    if rsi > 70:
        reasons.append(f"RSI at {rsi:.1f} — overbought territory, watch for pullback")
    elif rsi < 30:
        reasons.append(f"RSI at {rsi:.1f} — oversold territory, potential bounce zone")
    else:
        reasons.append(f"RSI at {rsi:.1f} — in neutral range")
    reasons.append(f"MACD is {macd} with a {trend} trend structure")
    if technical.atr:
        reasons.append(f"ATR at {technical.atr} — {'elevated' if technical.atr / price.current_price > 0.015 else 'normal'} volatility")

    # ── Risks from real data ───────────────────────────────────────────────────
    risks = []
    if rsi > 65:
        risks.append(f"RSI at {rsi:.1f} approaching overbought — reversal risk")
    if rsi < 35:
        risks.append(f"RSI at {rsi:.1f} in oversold zone — bounce not guaranteed")
    if chg < -2:
        risks.append(f"Sharp {chg:.2f}% decline may signal continued selling pressure")
    if chg > 2:
        risks.append(f"Strong {chg:.2f}% rally may face profit-taking near resistance")
    if macd == "BEARISH" and sentiment == "BULLISH":
        risks.append("MACD bearish divergence conflicts with price direction")
    if not risks:
        risks.append(f"Price near pivot {technical.pivot} — watch for breakout direction")
        risks.append("AI sentiment analysis unavailable — using technical signals only")

    # ── Target / stop from ATR or S/R ─────────────────────────────────────────
    atr = technical.atr or (price.current_price * 0.01)
    target    = round(price.current_price + atr * 2, 4) if direction == "UP"   else \
                round(price.current_price - atr * 2, 4) if direction == "DOWN" else None
    stop_loss = round(price.current_price - atr * 1.5, 4) if direction == "UP"   else \
                round(price.current_price + atr * 1.5, 4) if direction == "DOWN" else None

    return {
        "sentiment": sentiment,
        "confidence": confidence,
        "summary": (
            f"{price.symbol} is trading at {price.current_price} ({chg:+.2f}%). "
            f"Technical indicators show a {trend.lower()} trend with {macd.lower()} MACD "
            f"and RSI at {rsi:.1f}. Analysis based on technical signals only."
        ),
        "key_reasons": reasons,
        "support_levels": technical.supports,
        "resistance_levels": technical.resistances,
        "prediction": {
            "direction": direction,
            "timeframe": "1-3 days",
            "target": target,
            "stop_loss": stop_loss,
            "confidence": confidence,
        },
        "risks": risks,
        "news_sentiment": "NEUTRAL",
        "event_impact": "LOW",
    }
