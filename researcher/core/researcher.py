"""Main flow: validate, fetch, synthesize, save."""

from __future__ import annotations

from typing import Any

from researcher.concurrency import orchestrator
from researcher.models import ResearchRequest, ResearchResult


class ResearchError(RuntimeError):
    """Raised when no source returned anything usable."""


class Researcher:
    """Ties fetch and synthesis together."""

    def __init__(self, settings: Any, service: Any) -> None:
        self._settings = settings
        self._service = service

    async def ask(self, request: ResearchRequest) -> ResearchResult:
        """Fetch relevant sources and synthesize a cited answer."""
        question = request.question.strip()
        if not question:
            raise ValueError("question must not be blank")

        source_limit = min(
            request.max_sources_per_query,
            self._settings.max_sources_per_query,
        )
        requested_sources = request.sources[:source_limit]

        outcome = await orchestrator.fetch_all(
            question,
            requested_sources,
            self._settings,
            self._service,
        )

        if not outcome.sources:
            raise ResearchError("research failed because no source returned results")

        synthesized = self._service.synthesize(question, outcome.sources)

        warnings: list[str] = []
        if outcome.failures:
            failed_names = ", ".join(failure.source for failure in outcome.failures)
            successful_count = len(requested_sources) - len(outcome.failures)
            warnings.append(
                f"Only {successful_count}/{len(requested_sources)} sources succeeded; "
                f"failed sources: {failed_names}."
            )

        return ResearchResult(
            question=question,
            answer=synthesized.answer,
            citations=synthesized.citations,
            sources=outcome.sources,
            failures=outcome.failures,
            timings_ms=outcome.timings_ms,
            warnings=warnings,
        )