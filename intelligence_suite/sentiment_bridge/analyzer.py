"""
Sentiment Analyzer — Uses LLM to score headlines as bullish/bearish.
"""

import json
import logging
from datetime import datetime

import requests

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    def __init__(self, config: dict):
        self.config = config
        self.ollama_url = config.get("models", {}).get("gemma", {}).get(
            "url", "http://localhost:11434/api/generate"
        )
        self.model = config.get("models", {}).get("gemma", {}).get("model", "gemma4")

    def analyze_headlines(self, headlines: list[str], symbol: str = "") -> dict:
        """
        Send headlines to LLM and get aggregate sentiment score.

        Returns:
            dict with score (-1.0 to +1.0), individual scores, reasoning
        """
        if not headlines:
            return {"score": 0.0, "details": [], "symbol": symbol}

        # Batch headlines (max 15 to avoid token overflow)
        batch = headlines[:15]
        prompt = self._build_prompt(batch, symbol)

        try:
            resp = requests.post(
                self.ollama_url,
                json={
                    "model": self.model,
                    "system": (
                        "You are a financial sentiment analyst. "
                        "Score each headline from -1.0 (very bearish) to +1.0 (very bullish). "
                        "Respond with JSON only: {\"scores\": [float, ...], \"overall\": float, \"reasoning\": \"brief\"}"
                    ),
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.1, "num_predict": 1024},
                },
                timeout=60,
            )
            resp.raise_for_status()
            raw = resp.json()["response"].strip()
            result = self._parse(raw)
            result["symbol"] = symbol
            result["timestamp"] = datetime.now().isoformat()
            result["headline_count"] = len(batch)
            return result

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return {"score": 0.0, "details": [], "symbol": symbol, "error": str(e)}

    def _build_prompt(self, headlines: list[str], symbol: str) -> str:
        numbered = "\n".join(f"{i+1}. {h}" for i, h in enumerate(headlines))
        context = f" for {symbol}" if symbol else ""
        return f"""Score the sentiment{context} of these headlines (-1.0 bearish to +1.0 bullish):

{numbered}

Respond with JSON only."""

    def _parse(self, raw: str) -> dict:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = [l for l in cleaned.split("\n") if not l.strip().startswith("```")]
            cleaned = "\n".join(lines).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                data = json.loads(cleaned[start:end])
            else:
                return {"score": 0.0, "details": []}

        score = float(data.get("overall", 0))
        score = max(-1.0, min(1.0, score))
        return {
            "score": round(score, 3),
            "details": data.get("scores", []),
            "reasoning": data.get("reasoning", ""),
        }
