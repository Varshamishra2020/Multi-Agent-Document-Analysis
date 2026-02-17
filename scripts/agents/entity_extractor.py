"""
Entity extraction agent with LLM and heuristic fallback.
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
class Entity:
    name: str
    mentions: int
    context: Optional[str] = None
    role: Optional[str] = None
    type: Optional[str] = None


@dataclass
class EntitiesResult:
    people: list[Entity]
    organizations: list[Entity]
    dates: list[Entity]
    locations: list[Entity]


class EntityExtractorAgent:
    """
    Extract people, organizations, dates, and locations from documents.
    Fallback to heuristics when LLM is unavailable.
    """

    MAX_INPUT_CHARS = 6000
    
    ENTITY_PROMPT_TEMPLATE = (
        "You extract structured entities from documents. Respond with JSON containing "
        "people, organizations, dates, and locations arrays. Each entry needs name, mentions (int), "
        "context (short quote), and role/type when applicable."
    )

    COMPANY_HINTS = ("Inc", "Corp", "LLC", "Ltd", "Company", "Bank", "Group")
    LOCATION_HINTS = (
        "New York",
        "London",
        "Mumbai",
        "Delhi",
        "Singapore",
        "San Francisco",
        "Tokyo",
    )

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm_client = llm_client
        self._chain = None
        
        if llm_client and ChatPromptTemplate:
            try:
                prompt = ChatPromptTemplate.from_messages([
                    ("system", self.ENTITY_PROMPT_TEMPLATE),
                    ("human", "{document}"),
                ])
                self._chain = prompt | llm_client
            except Exception:
                pass

    async def run(self, document_text: str) -> EntitiesResult:
        if self._chain and document_text.strip():
            try:
                return await self._extract_llm(document_text)
            except Exception:
                pass
        # Use thread pool for Python 3.8 compatibility
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(_executor, self._extract, document_text)

    async def _extract_llm(self, text: str) -> EntitiesResult:
        response = await self._chain.ainvoke({"document": text[: self.MAX_INPUT_CHARS]})
        content = getattr(response, "content", response)
        if isinstance(content, list):
            content = " ".join(part["text"] for part in content if isinstance(part, dict) and "text" in part)
        payload = json.loads(content)

        def parse_entities(key: str, fallback_type: Optional[str] = None) -> list[Entity]:
            items = payload.get(key) or []
            entities: list[Entity] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                entities.append(
                    Entity(
                        name=item.get("name", "").strip(),
                        mentions=int(item.get("mentions", 1) or 1),
                        context=item.get("context", ""),
                        role=item.get("role"),
                        type=item.get("type", fallback_type),
                    )
                )
            return [entity for entity in entities if entity.name]

        return EntitiesResult(
            people=parse_entities("people"),
            organizations=parse_entities("organizations"),
            dates=parse_entities("dates"),
            locations=parse_entities("locations"),
        )

    def _extract(self, text: str) -> EntitiesResult:
        """Heuristic-based entity extraction fallback."""
        people = []
        organizations = []
        dates = []
        locations = []

        # Simple name pattern (capitalized words)
        name_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        names = re.findall(name_pattern, text)
        
        # Extract entities from matches
        seen_people = set()
        for name in names[:10]:
            if name not in seen_people and len(name.split()) <= 3:
                mentions = text.count(name)
                context = text[max(0, text.find(name) - 50):text.find(name) + len(name) + 50].strip()
                people.append(Entity(name=name, mentions=mentions, context=context, type="PERSON"))
                seen_people.add(name)

        # Extract organizations by hints
        for hint in self.COMPANY_HINTS:
            pattern = rf'\b[\w\s]*{hint}\b'
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                org_name = match.group(0).strip()
                if org_name and len(organizations) < 5:
                    mentions = text.count(org_name)
                    context = text[max(0, match.start() - 50):match.end() + 50].strip()
                    organizations.append(Entity(name=org_name, mentions=mentions, context=context, type="ORG"))

        # Extract locations by hints
        for location in self.LOCATION_HINTS:
            mentions = text.lower().count(location.lower())
            if mentions > 0:
                pattern = re.escape(location)
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    context = text[max(0, match.start() - 50):match.end() + 50].strip()
                    locations.append(Entity(name=location, mentions=mentions, context=context, type="LOCATION"))

        # Extract dates
        date_pattern = r'\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b'
        date_matches = re.finditer(date_pattern, text, re.IGNORECASE)
        seen_dates = set()
        for match in date_matches:
            date_text = match.group(0)
            if date_text not in seen_dates:
                mentions = text.count(date_text)
                context = text[max(0, match.start() - 50):match.end() + 50].strip()
                dates.append(Entity(name=date_text, mentions=mentions, context=context, type="DATE"))
                seen_dates.add(date_text)

        return EntitiesResult(
            people=people[:5],
            organizations=organizations[:5],
            dates=dates[:5],
            locations=locations[:5],
        )
