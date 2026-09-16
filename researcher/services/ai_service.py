"""All calls to ai go through here, with retries and logging."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Protocol

import httpx
from tenacity import (
    AsyncRetrying,
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ai import fetch_arxiv as _fetch_arxiv
from ai import fetch_web as _fetch_web
from ai import fetch_wikipedia as _fetch_wikipedia
from ai.providers.base import LLMProvider, ProviderError
from ai.schemas import AnswerWithCitations, Source
from ai.sources import DuckDuckGoProvider, SerperProvider, TavilyProvider, WebSearchProvider
from ai.synthesizer import synthesize as _ai_synthesize
from researcher.config import Settings, canonicalize_query
from researcher.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_RETRYABLE = (ProviderError, httpx.HTTPError, TimeoutError, OSError)

_FETCHERS: dict[str, Callable[..., Any]] = {
    "wikipedia": _fetch_wikipedia,
    "arxiv": _fetch_arxiv,
    "web": _fetch_web,
}


class CacheLike(Protocol):
    """The three cache methods this service needs.

    Emil's real store implements these. Tests use a small fake.
    A Protocol keeps this file working before his file lands.
    """

    def get(self, source: str, query: str) -> list[Source] | None: ...
    def set(self, source: str, query: str, value: list[Source]) -> None: ...
    def clear(self) -> None: ...


class ResilientAIService:
    """Wraps the ai package.

    The service holds settings, a cache and a limiter (composition,
    not inheritance: it uses them, it is not one of them).
    """

    def __init__(
        self,
        settings: Settings,
        cache: CacheLike,
        limiter: RateLimiter,
    ) -> None:
        self._settings = settings
        self._cache = cache
        self._limiter = limiter
        self._web_provider_cache: WebSearchProvider | None = None

    async def fetch_one(
        self,
        source: str,
        query: str,
        client: Any = None,
        use_cache: bool = True,
    ) -> list[Source]:
        """Fetch one source with cache, limit, timeout and retries."""
        name = source.strip().lower()
        if name not in _FETCHERS:
            raise ValueError(f"unknown source: {source!r}")
        if not query.strip():
            return []

        if use_cache:
            hit = self._cache.get(name, query)
            if hit is not None:
                logger.info("fetch cache_hit source=%s n=%d", name, len(hit))
                return hit

        await self._limiter.acquire()

        attempts = self._settings.retry_attempts

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(
                    multiplier=1,
                    min=self._settings.retry_min_wait,
                    max=self._settings.retry_max_wait,
                ),
                retry=retry_if_exception_type(_RETRYABLE),
                reraise=True,
            ):
                with attempt:
                    started = time.monotonic()
                    out = await asyncio.wait_for(
                        self._call_source(name, query, client),
                        timeout=self._settings.per_source_timeout_seconds,
                    )
                    ms = (time.monotonic() - started) * 1000
                    logger.info("fetch ok source=%s n=%d ms=%.0f", name, len(out), ms)
                    logger.debug("fetch payload source=%s items=%d", name, len(out))
                    self._cache.set(name, query, out)
                    return out
        except (ValueError, TypeError) as e:
            logger.warning("fetch bad_input source=%s error=%s", name, e)
            raise
        except Exception as e:
            logger.error("fetch failed source=%s error=%s", name, e)
            raise

        return []

    def _web_provider(self) -> WebSearchProvider:
        """Resolve the web-search provider from Settings (single source of
        truth) instead of relying on ai/sources.py's own os.getenv default."""
        if self._web_provider_cache is None:
            name = self._settings.web_search_provider
            if name == "tavily":
                self._web_provider_cache = TavilyProvider()
            elif name == "serper":
                self._web_provider_cache = SerperProvider()
            else:
                self._web_provider_cache = DuckDuckGoProvider()
        return self._web_provider_cache

    async def _call_source(
        self, name: str, query: str, client: Any
    ) -> list[Source]:
        key = canonicalize_query(query)
        shown = key[:80]
        logger.debug("fetch start source=%s q=%s", name, shown)
        limit = self._settings.max_sources_per_query

        if name == "wikipedia":
            return await _fetch_wikipedia(query, max_results=limit, client=client)
        if name == "arxiv":
            return await _fetch_arxiv(query, max_results=limit, client=client)
        return await _fetch_web(
            query,
            max_results=limit,
            client=client,
            provider=self._web_provider(),
        )

    def synthesize(
        self,
        question: str,
        sources: list[Source],
        llm: LLMProvider | None = None,
    ) -> AnswerWithCitations:
        """Ask the LLM for a cited answer. Retries with tenacity."""
        if not question.strip():
            raise ValueError("question must be non-empty")
        if not sources:
            raise ValueError("sources must be non-empty")

        attempts = max(self._settings.retry_attempts, 5)
        min_wait = max(self._settings.retry_min_wait, 10.0)
        max_wait = max(self._settings.retry_max_wait, 60.0)

        try:
            for attempt in Retrying(
                stop=stop_after_attempt(attempts),
                wait=wait_exponential(
                    multiplier=2,
                    min=min_wait,
                    max=max_wait,
                ),
                retry=retry_if_exception_type(_RETRYABLE),
                reraise=True,
            ):
                with attempt:
                    started = time.monotonic()
                    out = _ai_synthesize(question, sources, llm=llm)
                    ms = (time.monotonic() - started) * 1000
                    if not out.answer.strip():
                        raise ProviderError("LLM returned an empty answer")
                    logger.info(
                        "synthesize ok n_sources=%d answer_len=%d ms=%.0f",
                        len(sources),
                        len(out.answer),
                        ms,
                    )
                    logger.debug("synthesize answer=%s", out.answer[:2000])
                    return out
        except _RETRYABLE as e:
            logger.error("synthesize failed error=%s", e)
            raise