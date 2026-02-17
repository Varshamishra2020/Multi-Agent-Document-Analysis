"""
Sentiment analysis agent with LLM and heuristic fallback.
"""

from __future__ import annotations

import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Optional

try:
    from langchain_core.prompts import ChatPromptTemplate
except ImportError:
    ChatPromptTemplate = None

# Thread pool for compatibility with Python 3.8
_executor = ThreadPoolExecutor(max_workers=4)


POSITIVE_WORDS = {
    "growth",
    "improved",
    "record",
    "strong",
    "positive",
    "bullish",
    "expansion",
    "profit",
    "increase",
    "exceeded",
    "resilient",
    "excellent",
    "great",
    "good",
    "success",
    "benefit",
}

NEGATIVE_WORDS = {
    "decline",
    "drop",
    "loss",
    "negative",
    "weak",
    "missed",
    "risk",
    "volatility",
    "uncertain",
    "downturn",
    "slowdown",
    "failed",
    "bad",
    "poor",
    "challenge",
    "threat",
}


@dataclass
class SentimentResult:
    tone: str
    confidence: float
    formality: str
    key_phrases: list[str]


class SentimentAgent:
    """
    Analyze sentiment (tone, confidence, formality) of documents.
    Fallback to heuristics when LLM is unavailable.
    """

    MAX_INPUT_CHARS = 6000
    
    SENTIMENT_PROMPT_TEMPLATE = (
        "You evaluate documents for sentiment. Respond strictly as JSON with keys tone "
        "(positive/negative/neutral), confidence (0-1), formality (formal/informal), and "
        "key_phrases (array of 2-3 short quotes supporting the tone)."
    )

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm_client = llm_client
        self._chain = None
        
        if llm_client and ChatPromptTemplate:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self.SENTIMENT_PROMPT_TEMPLATE),
                    ("human", "{document}"),
                ])
                self._chain = prompt | llm_client
            except Exception:
                pass

    async def run(self, document_text: str) -> SentimentResult:
        if self._chain and document_text.strip():
            try:
                return await self._analyze_llm(document_text)
            except Exception:
                pass
        # Use thread pool for Python 3.8 compatibility
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._analyze, document_text)

    async def _analyze_llm(self, text: str) -> SentimentResult:
        response = await self._chain.ainvoke({"document": text[: self.MAX_INPUT_CHARS]})
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = " ".join(part["text"] for part in content if isinstance(part, dict) and "text" in part)
        payload = json.loads(content)
        tone = payload.get("tone", "neutral").lower()
        confidence = float(payload.get("confidence", 0.85))
        formality = payload.get("formality", "formal").lower()
        key_phrases = payload.get("key_phrases") or payload.get("keyPhrases") or []
        key_phrases = [kp.strip() for kp in key_phrases if isinstance(kp, str) and kp.strip()][:3]
        return SentimentResult(
            tone=tone,
            confidence=round(confidence, 2),
            formality=formality,
            key_phrases=key_phrases,
        )

    def _analyze(self, text: str) -> SentimentResult:
        """Heuristic-based sentiment analysis fallback."""
        if not text:
            return SentimentResult(tone="neutral", confidence=0.0, formality="formal", key_phrases=[])

        text_lower = text.lower()
        positive_count = sum(1 for word in POSITIVE_WORDS if word in text_lower)
        negative_count = sum(1 for word in NEGATIVE_WORDS if word in text_lower)

        if positive_count > negative_count:
            tone = "positive"
        elif negative_count > positive_count:
            tone = "negative"
        else:
            tone = "neutral"

        total_sentiment_words = positive_count + negative_count
        confidence = min(0.95, 0.5 + (total_sentiment_words / max(len(text.split()), 1) * 0.2))

        # Detect formality
        informal_markers = r"\b(gonna|wanna|hey|wow|amazing|awesome|lol)\b"
        if re.search(informal_markers, text_lower):
            formality = "informal"
        else:
            formality = "formal"

        # Extract key phrases
        sentences = re.split(r"[.!?]", text)
        key_phrases = [s.strip() for s in sentences if s.strip()][:3]

        return SentimentResult(
            tone=tone,
            confidence=round(confidence, 2),
            formality=formality,
            key_phrases=key_phrases,
        )
