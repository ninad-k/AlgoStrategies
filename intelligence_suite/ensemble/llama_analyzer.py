"""
LLaMA 3 Analyzer — Alternative LLM via Ollama for ensemble diversity.
Uses a different system prompt tuned for conservative analysis.
"""

import json
import logging
from datetime import datetime

import requests

from .base_analyzer import BaseAnalyzer

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a conservative crypto trading analyst. You analyze 1-minute candle data and provide careful, risk-aware trade decisions.

YOUR APPROACH:
1. You are CONSERVATIVE — only take trades with strong confluence (3+ indicators agreeing).
2. Prioritize RISK MANAGEMENT over profits.
3. HOLD when signals are mixed or volume is low. Better to miss a trade than take a bad one.
4. Key filters:
   - ADX > 25 required for trend trades
   - Volume must be ABOVE_AVG or higher
   - RSI extremes (<25 or >75) need candlestick confirmation
   - Ichimoku cloud breakouts need volume confirmation
5. SL: 1.0-1.5 ATR (generous). TP: 1.5-2.5 ATR (let winners run).
6. confidence must be a decimal 0.0-1.0.

JSON Response Format:
{"action": "BUY|SELL|HOLD", "confidence": 0.75, "sl_distance_atr": 1.2, "tp_distance_atr": 2.0, "reason": "concise reason"}"""


class LlamaAnalyzer(BaseAnalyzer):
    name = "llama"

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
        model_cfg = config.get("models", {}).get("llama", self.model_config)
        prompt = self._build_prompt(market_data)

        try:
            response = requests.post(
                model_cfg["url"],
                json={
                    "model": model_cfg["model"],
                    "system": SYSTEM_PROMPT,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": model_cfg.get("temperature", 0.1),
                        "num_predict": model_cfg.get("num_predict", 4096),
                    },
                },
                timeout=model_cfg.get("timeout", 120),
            )
            response.raise_for_status()
            raw = response.json()["response"].strip()
            decision = self._parse(raw)
            decision["model_name"] = "llama"
            decision["timestamp"] = datetime.now().isoformat()
            decision["symbol"] = market_data.get("symbol", "UNKNOWN")
            decision["raw_response"] = raw
            return self._validate(decision)

        except requests.exceptions.Timeout:
            return self._hold("timeout")
        except requests.exceptions.ConnectionError:
            return self._hold("connection_error")
        except Exception as e:
            logger.error(f"LLaMA analysis failed: {e}")
            return self._hold(str(e))

    def _build_prompt(self, data: dict) -> str:
        return f"""Analyze {data.get('symbol', '?')} on {data.get('timeframe', '1m')}.

PRICE: Close={data.get('close')} | ATR={data.get('atr')}
TREND: {data.get('trend')} | ADX={data.get('adx')} | Supertrend={data.get('supertrend')}
ICHIMOKU: Signal={data.get('ichimoku_signal')} | Cloud={data.get('ichimoku_cloud_color')}
MOMENTUM: RSI={data.get('rsi')} | MACD Hist={data.get('macd_hist')} | CCI={data.get('cci')} | MFI={data.get('mfi')}
VOLATILITY: BB Position={data.get('bb_pos')} | BB Width={data.get('bb_width')}%
VOLUME: {data.get('vol_trend')} ({data.get('vol_ratio')}x) | Patterns: {data.get('candle_patterns')}
S/R: Support={data.get('nearest_support')} | Resistance={data.get('nearest_resistance')}
EMA Cross: {data.get('ema_cross')} | PSAR: {data.get('psar_signal')}

Respond with JSON only."""

    def _parse(self, raw: str) -> dict:
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
            raise

    def _validate(self, d: dict) -> dict:
        if d.get("action", "").upper() not in {"BUY", "SELL", "HOLD"}:
            d["action"] = "HOLD"
            d["confidence"] = 0.0
        else:
            d["action"] = d["action"].upper()

        raw_conf = d.get("confidence", 0)
        if isinstance(raw_conf, str):
            raw_conf = 0.5
        d["confidence"] = max(0.0, min(1.0, float(raw_conf)))
        d.setdefault("sl_distance_atr", 1.2)
        d.setdefault("tp_distance_atr", 2.0)
        d.setdefault("reason", "no reason given")
        d["sl_distance_atr"] = max(0.5, min(2.0, float(d["sl_distance_atr"])))
        d["tp_distance_atr"] = max(0.75, min(3.0, float(d["tp_distance_atr"])))
        return d

    def _hold(self, reason: str) -> dict:
        return {
            "action": "HOLD", "confidence": 0.0,
            "sl_distance_atr": 0, "tp_distance_atr": 0,
            "reason": reason, "model_name": "llama",
            "timestamp": datetime.now().isoformat(), "symbol": "UNKNOWN",
        }
