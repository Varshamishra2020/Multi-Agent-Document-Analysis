"""
Orchestrator service that runs all agents in parallel and tracks execution.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Awaitable, Callable, Dict, Tuple

from agents.entity_extractor import EntityExtractorAgent
from agents.sentiment import SentimentAgent
from agents.summarizer import SummarizerAgent

AgentCallable = Callable[[str], Awaitable[Any]]


@dataclass
class AgentOutcome:
    name: str
    success: bool
    payload: Any
    processing_time_seconds: float
    error: str | None = None


class AnalysisOrchestrator:
    """
    Run all agents in parallel and return structured results with execution metrics.
    """

    def __init__(
        self,
        summarizer: SummarizerAgent,
        entity_extractor: EntityExtractorAgent,
        sentiment_analyzer: SentimentAgent,
    ) -> None:
        self._summarizer = summarizer
        self._entity_extractor = entity_extractor
        self._sentiment_analyzer = sentiment_analyzer

    async def run(self, document_text: str) -> Tuple[Dict[str, Any], Dict[str, AgentOutcome]]:
        """
        Run all agents in parallel and collect results.
        Returns: (structured_results, agent_outcomes)
        """
        # Run all agents concurrently
        tasks = [
            self._run_summary(document_text),
            self._run_entities(document_text),
            self._run_sentiment(document_text),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=False)
        
        agent_outcomes: Dict[str, AgentOutcome] = {}
        for outcome in results:
            if isinstance(outcome, AgentOutcome):
                agent_outcomes[outcome.name] = outcome

        # Build structured output
        structured: Dict[str, Any] = {}
        for name, outcome in agent_outcomes.items():
            if outcome.success:
                payload = (
                    asdict(outcome.payload) if is_dataclass(outcome.payload) else outcome.payload
                ) or {}
                payload["processing_time_seconds"] = outcome.processing_time_seconds
                structured[name] = payload
            else:
                structured[name] = {
                    "error": outcome.error,
                    "processing_time_seconds": outcome.processing_time_seconds,
                }

        return structured, agent_outcomes

    async def _run_summary(self, document_text: str) -> AgentOutcome:
        return await self._timed("summary", self._summarizer.run, document_text)

    async def _run_entities(self, document_text: str) -> AgentOutcome:
        return await self._timed("entities", self._entity_extractor.run, document_text)

    async def _run_sentiment(self, document_text: str) -> AgentOutcome:
        return await self._timed("sentiment", self._sentiment_analyzer.run, document_text)

    async def _timed(
        self,
        name: str,
        fn: AgentCallable,
        document_text: str,
    ) -> AgentOutcome:
        start = time.perf_counter()
        try:
            payload = await fn(document_text)
            success = True
            error = None
        except Exception as exc:
            payload = None
            success = False
            error = str(exc)

        elapsed = time.perf_counter() - start
        return AgentOutcome(
            name=name,
            success=success,
            payload=payload,
            processing_time_seconds=round(elapsed, 3),
            error=error,
        )
