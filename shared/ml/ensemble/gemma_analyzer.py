"""
Gemma 4 Analyzer — Sends market data to Gemma 4 via Ollama.
Adapted from execution/gemma_trader/gemma_analyzer.py.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import requests

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an AI crypto scalping bot. You analyze 1-minute candle data across 30+ technical indicators and make precise, profitable trade decisions on cryptocurrency CFDs.

INSTRUMENTS (all 24/7 crypto CFDs):
- BTCUSD: Bitcoin — highest liquidity, drives market sentiment.
- ETHUSD: Ethereum — correlates with BTC, has DeFi catalysts.
- LTCUSD: Litecoin — often leads BTC moves, lower liquidity.
- XRPUSD: Ripple — news-driven, regulatory sensitive.
- SOLUSD: Solana — high-beta, amplifies BTC moves 2-3x.

RULES:
1. Crypto trades 24/7 — there is ALWAYS opportunity. Do NOT default to HOLD.
2. Be AGGRESSIVE — take BUY/SELL when 2+ signals align.
3. Look for confluence: 2-3 indicators agreeing (RSI + MACD + Ichimoku + pattern).
4. Key signals: Ichimoku Cloud, MACD histogram, volume surges, candlestick patterns at S/R, Supertrend + EMA alignment.
5. Use ATR for SL/TP: SL 0.5-1.5 ATR, TP 1.0-2.0 ATR.
6. Only take trades where reward > risk.
7. confidence must be a decimal 0.0-1.0 (NOT a string).

JSON Response Format:
{"action": "BUY|SELL|HOLD", "confidence": 0.85, "sl_distance_atr": 1.0, "tp_distance_atr": 1.5, "reason": "concise 1-line reason"}"""


class GemmaAnalyzer(BaseAnalyzer):
    name = "gemma"

    def __init__(self, model_config: dict = None):
        self.model_config = model_config or {}

    def is_available(self) -> bool:
        url = self.model_config.get("url", "http://localhost:11434/api/generate")
        try:
            resp = requests.get(url.replace("/api/generate", "/api/tags"), timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def analyze(self, market_data: dict, config: dict) -> dict:
        model_cfg = config.get("models", {}).get("gemma", self.model_config)
        prompt = _build_prompt(market_data)

        adaptive_context = _load_adaptive_context(config)
        system = SYSTEM_PROMPT
        if adaptive_context:
            system += "\n\n" + adaptive_context

        try:
            response = requests.post(
                model_cfg["url"],
                json={
                    "model": model_cfg["model"],
                    "system": system,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": model_cfg.get("temperature", 0.1),
                        "num_predict": model_cfg.get("num_predict", 8192),
                    },
                },
                timeout=model_cfg.get("timeout", 120),
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()
            decision = _parse_response(raw)
            decision["model_name"] = "gemma"
            decision["timestamp"] = datetime.now().isoformat()
            decision["symbol"] = market_data.get("symbol", "UNKNOWN")
            decision["raw_response"] = raw
            return _validate(decision)

        except requests.exceptions.Timeout:
            return _hold("gemma", "timeout")
        except requests.exceptions.ConnectionError:
            return _hold("gemma", "connection_error")
        except Exception as e:
            logger.error(f"Gemma analysis failed: {e}")
            return _hold("gemma", str(e))


def _build_prompt(data: dict) -> str:
    symbol = data.get("symbol", "UNKNOWN")
    tf = data.get("timeframe", "1m")
    return f"""Analyze {symbol} on {tf} timeframe. Make a trade decision.

PRICE ACTION:
  Close: {data.get('close')} | Open: {data.get('open')} | High: {data.get('high')} | Low: {data.get('low')}
  Last 5 Candles: {data.get('last_5_candles', 'N/A')}
  Candlestick Patterns: {data.get('candle_patterns', 'NONE')}
  Support: {data.get('nearest_support', 'N/A')} | Resistance: {data.get('nearest_resistance', 'N/A')}

TREND:
  EMA(9): {data.get('ema9')} | EMA(20): {data.get('ema20')} | EMA(50): {data.get('ema50')} | EMA(200): {data.get('ema200')}
  Trend: {data.get('trend')} | EMA Cross: {data.get('ema_cross', 'NONE')}
  ADX: {data.get('adx')} | DI+: {data.get('di_plus')} | DI-: {data.get('di_minus')}
  Supertrend: {data.get('supertrend', 'N/A')} | PSAR: {data.get('psar_signal', 'N/A')}

ICHIMOKU:
  Tenkan: {data.get('ichimoku_tenkan')} | Kijun: {data.get('ichimoku_kijun')}
  Span A: {data.get('ichimoku_span_a')} | Span B: {data.get('ichimoku_span_b')}
  Signal: {data.get('ichimoku_signal', 'N/A')} | Cloud: {data.get('ichimoku_cloud_color', 'N/A')}

MOMENTUM:
  RSI(14): {data.get('rsi')} | MACD Hist: {data.get('macd_hist')}
  Stoch RSI K: {data.get('stoch_rsi_k')} | CCI: {data.get('cci')} | Williams %R: {data.get('williams_r')}
  MFI: {data.get('mfi')}

VOLATILITY:
  ATR(14): {data.get('atr')} | BB Position: {data.get('bb_pos')} | BB Width: {data.get('bb_width')}%

VOLUME:
  Trend: {data.get('vol_trend')} ({data.get('vol_ratio', '?')}x avg) | VWAP: {data.get('vwap')}

Respond with JSON only."""


def _load_adaptive_context(config: dict) -> str:
    try:
        ctx_path = Path(config.get("logging", {}).get("adaptive_context", "logs/adaptive_context.txt"))
        if ctx_path.exists():
            text = ctx_path.read_text().strip()
            if text:
                return f"ADAPTIVE CONTEXT (lessons from past trades):\n{text}"
    except Exception:
        pass
    return ""


def _parse_response(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = [l for l in cleaned.split("\n") if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}") + 1
        if start != -1 and end > start:
            return json.loads(cleaned[start:end])
        raise ValueError(f"Could not parse JSON from response")


def _validate(decision: dict) -> dict:
    valid_actions = {"BUY", "SELL", "HOLD"}
    if decision.get("action", "").upper() not in valid_actions:
        decision["action"] = "HOLD"
        decision["confidence"] = 0.0
    else:
        decision["action"] = decision["action"].upper()

    raw_conf = decision.get("confidence", 0)
    if isinstance(raw_conf, str):
        conf_map = {"very low": 0.15, "low": 0.3, "medium": 0.5, "high": 0.75, "very high": 0.9}
        conf = conf_map.get(raw_conf.strip().lower(), 0.5)
    else:
        conf = float(raw_conf)
    decision["confidence"] = max(0.0, min(1.0, conf))

    decision.setdefault("sl_distance_atr", 1.0)
    decision.setdefault("tp_distance_atr", 1.5)
    decision.setdefault("reason", "no reason given")
    decision["sl_distance_atr"] = max(0.5, min(2.0, float(decision["sl_distance_atr"])))
    decision["tp_distance_atr"] = max(0.75, min(3.0, float(decision["tp_distance_atr"])))
    return decision


def _hold(model_name: str, reason: str) -> dict:
    return {
        "action": "HOLD", "confidence": 0.0,
        "sl_distance_atr": 0, "tp_distance_atr": 0,
        "reason": reason, "model_name": model_name,
        "timestamp": datetime.now().isoformat(), "symbol": "UNKNOWN",
    }
