"""Runs the three source fetches together."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ai.schemas import Source
from researcher.config import Settings
from researcher.models import SourceFailure

logger = logging.getLogger(__name__)

_ALIASES = {"wiki": "wikipedia", "wikipedia": "wikipedia", "arxiv": "arxiv", "web": "web"}


class AIServiceLike(Protocol):
    """The one method the orchestrator needs from ResilientAIService.

    A Protocol so this file doesn't have to import the real service (and
    its retry/tenacity dependency) just to type-check. Tests use a fake.
    """

    async def fetch_one(self, source: str, query: str, client: Any = None) -> list[Source]: ...


@dataclass(frozen=True)
class FetchOutcome:
    sources: list[Source]
    failures: list[SourceFailure]
    timings_ms: dict[str, float]


async def _fetch_one(
    source: str,
    question: str,
    settings: Settings,
    svc: AIServiceLike,
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
) -> tuple[str, list[Source] | Exception, float]:
    started = time.monotonic()
    async with sem:
        try:
            async with asyncio.timeout(settings.per_source_timeout_seconds):
                result = await svc.fetch_one(source, question, client=client)
            return source, result, (time.monotonic() - started) * 1000
        except Exception as e:
            return source, e, (time.monotonic() - started) * 1000


async def fetch_all(
    question: str,
    sources: tuple[str, ...],
    settings: Settings,
    svc: AIServiceLike,
) -> FetchOutcome:
    if not question.strip():
        return FetchOutcome(sources=[], failures=[], timings_ms={})

    resolved: list[str] = []
    for s in sources:
        name = s.strip().lower()
        if name not in _ALIASES:
            raise ValueError(f"unknown source: {s!r}")
        resolved.append(_ALIASES[name])

    sem = asyncio.Semaphore(settings.max_parallel)

    async with httpx.AsyncClient(timeout=settings.per_source_timeout_seconds) as client:
        results = await asyncio.gather(
            *(_fetch_one(src, question, settings, svc, client, sem) for src in resolved)
        )

    all_sources: list[Source] = []
    failures: list[SourceFailure] = []
    timings_ms: dict[str, float] = {}

    for source, outcome, ms in results:
        timings_ms[source] = round(ms, 1)
        if isinstance(outcome, Exception):
            logger.info("source failed source=%s ms=%.0f error=%s", source, ms, outcome)
            failures.append(SourceFailure(source=source, error=str(outcome)))
            continue
        logger.info("source ok source=%s ms=%.0f n=%d", source, ms, len(outcome))
        all_sources.extend(outcome)

    return FetchOutcome(sources=all_sources, failures=failures, timings_ms=timings_ms)