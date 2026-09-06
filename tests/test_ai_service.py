"""Tests for the resilient wrapper around ai. All offline."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest

from ai.providers.base import LLMProvider, ProviderError
from ai.schemas import Source
from researcher.config import Settings, canonicalize_query
from researcher.services.ai_service import ResilientAIService
from researcher.services.rate_limit import NoopLimiter


def _settings(**over: Any) -> Settings:
    base: dict[str, Any] = {
        "llm_provider": "gemini",
        "llm_model": "test-model",
        "web_search_provider": "duckduckgo",
        "log_level": "WARNING",
        "cache_dir": Path("./.cache"),
        "cache_ttl_seconds": 60,
        "per_source_timeout_seconds": 5.0,
        "max_sources_per_query": 2,
        "max_parallel": 5,
        "retry_attempts": 3,
        "retry_min_wait": 0.01,
        "retry_max_wait": 0.05,
        "database_url": "sqlite:///./test.db",
    }
    base.update(over)
    return Settings(**base)


class FakeCache:
    """Same methods as the real store, kept in memory."""

    def __init__(self) -> None:
        self._data: dict[tuple[str, str], list[Source]] = {}
        self.get_calls = 0

    def get(self, source: str, query: str) -> list[Source] | None:
        self.get_calls += 1
        return self._data.get((source, canonicalize_query(query)))

    def set(self, source: str, query: str, value: list[Source]) -> None:
        self._data[(source, canonicalize_query(query))] = value

    def clear(self) -> None:
        self._data.clear()


def _source(title: str = "T", origin: str = "web") -> Source:
    return Source(
        title=title,
        url="https://example.com/x",
        snippet="some text",
        origin=origin,  # type: ignore[arg-type]
    )


def _svc(**over: Any) -> tuple[ResilientAIService, FakeCache]:
    cache = FakeCache()
    svc = ResilientAIService(_settings(**over), cache, NoopLimiter())
    return svc, cache


@pytest.mark.asyncio
async def test_blank_query_returns_empty_without_network(monkeypatch: Any) -> None:
    svc, cache = _svc()
    called = False

    async def _fail(*a: Any, **k: Any) -> list[Source]:
        nonlocal called
        called = True
        return [_source()]

    monkeypatch.setattr("researcher.services.ai_service._fetch_wikipedia", _fail)
    out = await svc.fetch_one("wikipedia", "   ")
    assert out == []
    assert called is False


@pytest.mark.asyncio
async def test_bad_source_raises() -> None:
    svc, _ = _svc()
    with pytest.raises(ValueError):
        await svc.fetch_one("reddit", "something")


@pytest.mark.asyncio
async def test_second_call_hits_cache(monkeypatch: Any) -> None:
    svc, cache = _svc()
    calls = 0

    async def _fake(query: str, *, max_results: int = 2, client: Any = None) -> list[Source]:
        nonlocal calls
        calls += 1
        return [_source("Cached")]

    monkeypatch.setattr("researcher.services.ai_service._fetch_wikipedia", _fake)
    first = await svc.fetch_one("wikipedia", "Photosynthesis")
    second = await svc.fetch_one("wikipedia", "photosynthesis  ")
    assert len(first) == 1
    assert second == first
    assert calls == 1
    assert cache.get_calls >= 2


@pytest.mark.asyncio
async def test_no_cache_flag_skips_cache(monkeypatch: Any) -> None:
    svc, _ = _svc()
    calls = 0

    async def _fake(query: str, *, max_results: int = 2, client: Any = None) -> list[Source]:
        nonlocal calls
        calls += 1
        return [_source("Fresh")]

    monkeypatch.setattr("researcher.services.ai_service._fetch_arxiv", _fake)
    await svc.fetch_one("arxiv", "fusion")
    await svc.fetch_one("arxiv", "fusion", use_cache=False)
    assert calls == 2


@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch: Any) -> None:
    svc, _ = _svc()
    calls = 0

    async def _flaky(query: str, *, max_results: int = 2, client: Any = None) -> list[Source]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ProviderError("tmp down")
        return [_source("Late")]

    monkeypatch.setattr("researcher.services.ai_service._fetch_web", _flaky)
    out = await svc.fetch_one("web", "fusion")
    assert len(out) == 1
    assert calls == 3


@pytest.mark.asyncio
async def test_gives_up_after_attempts(monkeypatch: Any) -> None:
    svc, _ = _svc(retry_attempts=2)
    calls = 0

    async def _down(query: str, *, max_results: int = 2, client: Any = None) -> list[Source]:
        nonlocal calls
        calls += 1
        raise ProviderError("still down")

    monkeypatch.setattr("researcher.services.ai_service._fetch_web", _down)
    with pytest.raises(ProviderError):
        await svc.fetch_one("web", "fusion")
    assert calls == 2


@pytest.mark.asyncio
async def test_timeout_counts_as_retry(monkeypatch: Any) -> None:
    svc, _ = _svc(retry_attempts=2, per_source_timeout_seconds=0.05)

    async def _slow(query: str, *, max_results: int = 2, client: Any = None) -> list[Source]:
        await asyncio.sleep(5)
        return [_source()]

    monkeypatch.setattr("researcher.services.ai_service._fetch_wikipedia", _slow)
    with pytest.raises(Exception):
        await svc.fetch_one("wikipedia", "slow query")


class _FixedLLM(LLMProvider):
    def __init__(self, text: str) -> None:
        self.text = text

    def complete(
        self,
        prompt: str,
        *,
        json_schema: dict | None = None,
        max_tokens: int = 1024,
    ) -> str:
        return self.text


def test_synthesize_happy_path(sample_sources: list[Source]) -> None:
    svc, _ = _svc()
    llm = _FixedLLM("Plants do this [1] and that [2].")
    out = svc.synthesize("What is photosynthesis?", sample_sources, llm=llm)
    assert out.answer.startswith("Plants")
    assert {c.index for c in out.citations} == {1, 2}


def test_synthesize_rejects_bad_input(sample_sources: list[Source]) -> None:
    svc, _ = _svc()
    llm = _FixedLLM("answer [1]")
    with pytest.raises(ValueError):
        svc.synthesize("   ", sample_sources, llm=llm)
    with pytest.raises(ValueError):
        svc.synthesize("question?", [], llm=llm)


def test_synthesize_retries_on_provider_error(sample_sources: list[Source]) -> None:
    svc, _ = _svc()
    calls = 0

    class _Flaky(LLMProvider):
        def complete(self, prompt: str, *, json_schema=None, max_tokens=1024) -> str:  # type: ignore[no-untyped-def]
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ProviderError("tmp down")
            return "Plants do this [1]."

    out = svc.synthesize("Q?", sample_sources, llm=_Flaky())
    assert "[1]" in out.answer
    assert calls == 2


def test_synthesize_rejects_empty_answer(sample_sources: list[Source]) -> None:
    svc, _ = _svc()
    with pytest.raises(ProviderError):
        svc.synthesize("Q?", sample_sources, llm=_FixedLLM("   "))
