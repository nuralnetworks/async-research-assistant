"""Tests for request and result models."""

from __future__ import annotations

import pytest

from researcher.models import ResearchRequest, ResearchResult


def test_defaults_are_sensible() -> None:
    req = ResearchRequest(question="What is photosynthesis?")
    assert req.sources == ("wikipedia", "arxiv", "web")
    assert req.use_cache is True
    assert req.max_sources_per_query == 3


def test_question_is_stripped() -> None:
    req = ResearchRequest(question="  hello world  ")
    assert req.question == "hello world"


def test_short_question_rejected() -> None:
    with pytest.raises(ValueError):
        ResearchRequest(question="  ")


def test_long_question_rejected() -> None:
    with pytest.raises(ValueError):
        ResearchRequest(question="x" * 2001)


def test_bad_source_rejected() -> None:
    with pytest.raises(ValueError):
        ResearchRequest(question="valid question here", sources=("reddit",))  # type: ignore[arg-type]


def test_wiki_alias_becomes_wikipedia() -> None:
    req = ResearchRequest(question="valid question here", sources=("wiki", "arxiv"))  # type: ignore[arg-type]
    assert req.sources == ("wikipedia", "arxiv")


def test_duplicate_sources_removed() -> None:
    req = ResearchRequest(
        question="valid question here",
        sources=("web", "web", "arxiv"),
    )
    assert req.sources == ("web", "arxiv")


def test_result_defaults_to_empty_lists() -> None:
    res = ResearchResult(question="q", answer="a")
    assert res.sources == []
    assert res.failures == []
    assert res.warnings == []
    assert res.cache_hit is False
