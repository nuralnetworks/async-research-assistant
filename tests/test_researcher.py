"""Offline contract tests for the core research pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any, Awaitable, Callable

import pytest

from ai.schemas import AnswerWithCitations, Citation, Source
from researcher.core import researcher as researcher_module
from researcher.core.researcher import ResearchError, Researcher
from researcher.models import ResearchRequest, SourceFailure

FetchBehavior = Callable[
    [str, tuple[str, ...], Any, Any],
    Awaitable["FakeFetchOutcome"],
]


@dataclass(frozen=True)
class FakeFetchOutcome:
    """Offline equivalent of the orchestrator's FetchOutcome."""

    sources: list[Source]
    failures: list[SourceFailure] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)


class FakeHistoryRecorder:
    """Records successful synthesis calls without persistent storage."""

    def __init__(self) -> None:
        self.entries: list[tuple[str, list[Source]]] = []

    def record(self, question: str, sources: list[Source]) -> None:
        self.entries.append((question, list(sources)))


class FakeAIService:
    """Deterministic AI service that never calls an external provider."""

    def __init__(
        self,
        answer: AnswerWithCitations,
        history: FakeHistoryRecorder,
    ) -> None:
        self._answer = answer
        self._history = history
        self.synthesize_calls: list[tuple[str, list[Source]]] = []

    def synthesize(
        self,
        question: str,
        sources: list[Source],
        llm: Any = None,
    ) -> AnswerWithCitations:
        del llm

        copied_sources = list(sources)
        self.synthesize_calls.append((question, copied_sources))
        self._history.record(question, copied_sources)
        return self._answer


WIKIPEDIA_SOURCE = Source(
    title="Asynchronous I/O",
    url="https://example.test/wikipedia/async-io",
    snippet="Asynchronous I/O allows other work while an operation is waiting.",
    origin="wikipedia",
)

ARXIV_SOURCE = Source(
    title="Structured Concurrency",
    url="https://example.test/arxiv/structured-concurrency",
    snippet="Structured concurrency organizes related asynchronous tasks.",
    origin="arxiv",
)

WEB_SOURCE = Source(
    title="Async Programming Guide",
    url="https://example.test/web/async-guide",
    snippet="Concurrent tasks can improve throughput for I/O-bound workloads.",
    origin="web",
)

QUESTION = "How does asynchronous I/O improve throughput?"

CANNED_ANSWER = AnswerWithCitations(
    question=QUESTION,
    answer="Asynchronous I/O improves throughput by overlapping waiting periods [1].",
    citations=[
        Citation(
            index=1,
            source=WIKIPEDIA_SOURCE,
        )
    ],
)


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        max_sources_per_query=3,
        max_parallel=3,
        per_source_timeout_seconds=1.0,
    )


def _request() -> ResearchRequest:
    return ResearchRequest(question=QUESTION)



def _install_fetch_behavior(
    monkeypatch: pytest.MonkeyPatch,
    behavior: FetchBehavior,
) -> None:
    monkeypatch.setattr(
        "researcher.core.researcher.fetch_all",
        behavior,
        raising=False,
    )



@pytest.mark.asyncio
async def test_happy_path_produces_answer_and_citation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(
        question: str,
        sources: tuple[str, ...],
        settings: Any,
        svc: Any,
    ) -> FakeFetchOutcome:
        del settings, svc
        assert question == QUESTION
        assert sources == ("wikipedia", "arxiv", "web")

        return FakeFetchOutcome(
            sources=[WIKIPEDIA_SOURCE, ARXIV_SOURCE, WEB_SOURCE],
            timings_ms={
                "wikipedia": 4.0,
                "arxiv": 5.0,
                "web": 6.0,
            },
        )

    _install_fetch_behavior(monkeypatch, fake_fetch_all)

    history = FakeHistoryRecorder()
    service = FakeAIService(CANNED_ANSWER, history)
    researcher = Researcher(_settings(), service)

    result = await researcher.ask(_request())

    assert result.answer
    assert "[1]" in result.answer
    assert [citation.index for citation in result.citations] == [1]
    assert result.sources == [
        WIKIPEDIA_SOURCE,
        ARXIV_SOURCE,
        WEB_SOURCE,
    ]
    assert result.failures == []
    assert result.warnings == []
    assert result.timings_ms == {
        "wikipedia": 4.0,
        "arxiv": 5.0,
        "web": 6.0,
    }

    assert service.synthesize_calls == [
        (
            QUESTION,
            [WIKIPEDIA_SOURCE, ARXIV_SOURCE, WEB_SOURCE],
        )
    ]
    assert history.entries == [
        (
            QUESTION,
            [WIKIPEDIA_SOURCE, ARXIV_SOURCE, WEB_SOURCE],
        )
    ]


@pytest.mark.asyncio
async def test_one_failed_source_still_produces_answer_and_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(
        question: str,
        sources: tuple[str, ...],
        settings: Any,
        svc: Any,
    ) -> FakeFetchOutcome:
        del question, sources, settings, svc

        return FakeFetchOutcome(
            sources=[WIKIPEDIA_SOURCE, WEB_SOURCE],
            failures=[
                SourceFailure(
                    source="arxiv",
                    error="provider unavailable",
                )
            ],
            timings_ms={
                "wikipedia": 4.0,
                "arxiv": 5.0,
                "web": 6.0,
            },
        )

    _install_fetch_behavior(monkeypatch, fake_fetch_all)

    history = FakeHistoryRecorder()
    service = FakeAIService(CANNED_ANSWER, history)
    researcher = Researcher(_settings(), service)

    result = await researcher.ask(_request())

    assert result.answer
    assert "[1]" in result.answer
    assert result.sources == [WIKIPEDIA_SOURCE, WEB_SOURCE]
    assert result.failures == [
        SourceFailure(
            source="arxiv",
            error="provider unavailable",
        )
    ]
    assert result.warnings
    assert any("arxiv" in warning.lower() for warning in result.warnings)
    assert any("2/3" in warning for warning in result.warnings)

    assert service.synthesize_calls == [
        (
            QUESTION,
            [WIKIPEDIA_SOURCE, WEB_SOURCE],
        )
    ]
    assert history.entries == [
        (
            QUESTION,
            [WIKIPEDIA_SOURCE, WEB_SOURCE],
        )
    ]


@pytest.mark.asyncio
async def test_all_sources_failing_raises_research_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_all(
        question: str,
        sources: tuple[str, ...],
        settings: Any,
        svc: Any,
    ) -> FakeFetchOutcome:
        del question, sources, settings, svc

        return FakeFetchOutcome(
            sources=[],
            failures=[
                SourceFailure(source="wikipedia", error="offline"),
                SourceFailure(source="arxiv", error="offline"),
                SourceFailure(source="web", error="offline"),
            ],
            timings_ms={
                "wikipedia": 1.0,
                "arxiv": 1.0,
                "web": 1.0,
            },
        )

    _install_fetch_behavior(monkeypatch, fake_fetch_all)

    history = FakeHistoryRecorder()
    service = FakeAIService(CANNED_ANSWER, history)
    researcher = Researcher(_settings(), service)

    with pytest.raises(ResearchError, match=r"(?i)(source|research|result)"):
        await researcher.ask(_request())

    assert service.synthesize_calls == []
    assert history.entries == []


@pytest.mark.asyncio
async def test_blank_question_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetch_was_called = False

    async def fake_fetch_all(
        question: str,
        sources: tuple[str, ...],
        settings: Any,
        svc: Any,
    ) -> FakeFetchOutcome:
        nonlocal fetch_was_called
        del question, sources, settings, svc

        fetch_was_called = True
        return FakeFetchOutcome(sources=[WIKIPEDIA_SOURCE])

    _install_fetch_behavior(monkeypatch, fake_fetch_all)

    history = FakeHistoryRecorder()
    service = FakeAIService(CANNED_ANSWER, history)
    researcher = Researcher(_settings(), service)

    # Bypass Pydantic validation to verify the core layer's defensive check.
    request = ResearchRequest.model_construct(
        question="   ",
        sources=("wikipedia",),
        use_cache=True,
        max_sources_per_query=1,
    )

    with pytest.raises(ValueError, match=r"(?i)(question|blank|empty)"):
        await researcher.ask(request)

    assert fetch_was_called is False
    assert service.synthesize_calls == []
    assert history.entries == []