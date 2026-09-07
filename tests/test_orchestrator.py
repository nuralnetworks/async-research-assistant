import asyncio
from pathlib import Path

import pytest

from ai.schemas import Source
from ai.providers.base import ProviderError
from researcher.config import Settings
from researcher.concurrency.orchestrator import fetch_all


def _settings(max_parallel=5, per_source_timeout_seconds=1.0):
    return Settings(
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-6",
        web_search_provider="duckduckgo",
        log_level="INFO",
        cache_dir=Path("./.cache"),
        cache_ttl_seconds=86400,
        per_source_timeout_seconds=per_source_timeout_seconds,
        max_sources_per_query=3,
        max_parallel=max_parallel,
        retry_attempts=3,
        retry_min_wait=1.0,
        retry_max_wait=8.0,
        database_url="sqlite:///./researcher.db",
    )


class _FakeSvc:
    def __init__(self, *, fail_sources=(), delay=0.05):
        self._fail_sources = set(fail_sources)
        self._delay = delay
        self.max_concurrent_seen = 0
        self._current = 0
        self._lock = asyncio.Lock()

    async def fetch_one(self, source, query, client=None):
        async with self._lock:
            self._current += 1
            self.max_concurrent_seen = max(self.max_concurrent_seen, self._current)
        try:
            await asyncio.sleep(self._delay)
            if source in self._fail_sources:
                raise ProviderError(f"{source} is down")
            return [Source(title=f"{source} title", url=f"https://{source}.example",
                            snippet="s", origin=source)]
        finally:
            async with self._lock:
                self._current -= 1


@pytest.mark.asyncio
async def test_happy_path_three_sources():
    svc = _FakeSvc()
    outcome = await fetch_all("what is X", ("wiki", "arxiv", "web"), _settings(), svc)

    assert len(outcome.sources) == 3
    assert outcome.failures == []
    assert set(outcome.timings_ms) == {"wikipedia", "arxiv", "web"}


@pytest.mark.asyncio
async def test_degraded_path_one_source_fails():
    svc = _FakeSvc(fail_sources={"arxiv"})
    outcome = await fetch_all("what is X", ("wiki", "arxiv", "web"), _settings(), svc)

    origins = {s.origin for s in outcome.sources}
    assert origins == {"wikipedia", "web"}
    assert len(outcome.failures) == 1
    assert outcome.failures[0].source == "arxiv"
    assert "down" in outcome.failures[0].error


@pytest.mark.asyncio
async def test_all_sources_fail_returns_failures_no_raise():
    svc = _FakeSvc(fail_sources={"wikipedia", "arxiv", "web"})
    outcome = await fetch_all("what is X", ("wiki", "arxiv", "web"), _settings(), svc)

    assert outcome.sources == []
    assert {f.source for f in outcome.failures} == {"wikipedia", "arxiv", "web"}


@pytest.mark.asyncio
async def test_semaphore_bounds_concurrency():
    svc = _FakeSvc(delay=0.05)
    settings = _settings(max_parallel=2)
    await fetch_all("q", ("wiki", "wiki", "arxiv", "arxiv", "web", "web"), settings, svc)
    assert svc.max_concurrent_seen <= 2


@pytest.mark.asyncio
async def test_blank_question_short_circuits_no_network():
    class _ExplodingSvc:
        async def fetch_one(self, *a, **kw):
            raise AssertionError("should not be called for a blank question")

    outcome = await fetch_all("   ", ("wiki",), _settings(), _ExplodingSvc())
    assert outcome.sources == []
    assert outcome.failures == []
    assert outcome.timings_ms == {}


@pytest.mark.asyncio
async def test_unknown_source_raises_before_network():
    class _ExplodingSvc:
        async def fetch_one(self, *a, **kw):
            raise AssertionError("should not be called for an unknown source")

    with pytest.raises(ValueError):
        await fetch_all("q", ("wiki", "not-a-real-source"), _settings(), _ExplodingSvc())


@pytest.mark.asyncio
async def test_per_source_timeout_becomes_a_failure():
    class _SlowSvc:
        async def fetch_one(self, source, query, client=None):
            await asyncio.sleep(1.0)
            return []

    settings = _settings(per_source_timeout_seconds=0.05)
    outcome = await fetch_all("q", ("wiki",), settings, _SlowSvc())
    assert outcome.sources == []
    assert len(outcome.failures) == 1
    assert outcome.failures[0].source == "wikipedia"