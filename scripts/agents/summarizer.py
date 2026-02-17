"""
Lightweight summarizer agent with LLM and heuristic fallback.
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


@dataclass
class SummaryResult:
    text: Optional[str]
    key_points: list[str]
    confidence: float


class SummarizerAgent:
    """
    Generate a concise summary and key points for the document.
    Fallback to heuristics when LLM is unavailable.
    """

    MAX_INPUT_CHARS = 6000
    
    SUMMARY_PROMPT_TEMPLATE = (
        "You are an expert analyst. Summarize the user's document in JSON with "
        "keys summary_text (<=150 words), key_points (array of 3-5 concise bullet strings), "
        "and confidence (0-1 float). Respond with JSON only."
    )

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm_client = llm_client
        self._chain = None
        
        if llm_client and ChatPromptTemplate:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self.SUMMARY_PROMPT_TEMPLATE),
                    ("human", "{document}"),
                ])
                self._chain = prompt | llm_client
            except Exception:
                pass

    async def run(self, document_text: str) -> SummaryResult:
        text = document_text.strip()
        if not text:
            return SummaryResult(text="", key_points=[], confidence=0.0)

        if self._chain:
            try:
                return await self._summarize_llm(text)
            except Exception:
                pass

        # Use thread pool for Python 3.8 compatibility
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._summarize, text)

    async def _summarize_llm(self, text: str) -> SummaryResult:
        try:
            response = await self._chain.ainvoke({"document": text[: self.MAX_INPUT_CHARS]})
            content = getattr(response, "content", response)
            if isinstance(content, list):
                content = " ".join(part["text"] for part in content if isinstance(part, dict) and "text" in part)
            payload = json.loads(content)
            summary_text = payload.get("summary_text") or payload.get("summary") or ""
            key_points = payload.get("key_points") or payload.get("keyPoints") or []
            confidence = float(payload.get("confidence", 0.85))

            key_points = [kp.strip() for kp in key_points if isinstance(kp, str) and kp.strip()][:5]
            words = summary_text.split()
            if len(words) > 150:
                summary_text = " ".join(words[:150]) + "..."

            return SummaryResult(text=summary_text.strip(), key_points=key_points, confidence=round(confidence, 2))
        except Exception:
            raise

    def _summarize(self, text: str) -> SummaryResult:
        """Heuristic-based summarization fallback."""
        if not text:
            return SummaryResult(text="", key_points=[], confidence=0.0)

        sentences = re.split(r"(?<=[.!?])\s+", text)
        trimmed_sentences = [s.strip() for s in sentences if s.strip()]
        summary_text = " ".join(trimmed_sentences[:3])

        words = summary_text.split()
        if len(words) > 150:
            summary_text = " ".join(words[:150]) + "..."

        key_points = trimmed_sentences[:5]
        confidence = min(0.95, 0.5 + len(summary_text) / max(len(text), 1))

        return SummaryResult(
            text=summary_text,
            key_points=key_points,
            confidence=round(confidence, 2),
        )
