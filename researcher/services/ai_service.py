"""All calls to ai go through here, with retries and logging."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any, Protocol

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from ai import fetch_arxiv as _fetch_arxiv
from ai import fetch_web as _fetch_web
from ai import fetch_wikipedia as _fetch_wikipedia
from ai.providers.base import LLMProvider, ProviderError
from ai.schemas import AnswerWithCitations, Source
from ai.synthesizer import synthesize as _ai_synthesize
from researcher.config import Settings, canonicalize_query
from researcher.services.rate_limit import RateLimiter

logger = logging.getLogger(__name__)

_RETRYABLE = (ProviderError, httpx.HTTPError, TimeoutError, OSError)

# Cache namespace. Bump when retrieval changes, so entries written by an
# older query logic are never served as if they were fresh.
_CACHE_VERSION = "v2"

# Leading words that add no meaning for keyword search. Stripped once.
_QUESTION_STARTS = (
    "what is",
    "what are",
    "what was",
    "what were",
    "what does",
    "what do",
    "what did",
    "who is",
    "who are",
    "who was",
    "when is",
    "when was",
    "where is",
    "where are",
    "why is",
    "why are",
    "why do",
    "why does",
    "how is",
    "how are",
    "how do",
    "how does",
    "how did",
    "how can",
    "how could",
    "explain",
    "describe",
    "define",
    "tell me",
)


def search_keywords(question: str) -> str:
    """Turn a question into keywords for Wikipedia and arXiv.

    Those two want short keyword queries; a full sentence like
    "What is photosynthesis?" comes back empty or off-topic.
    Web search keeps the original question, it likes sentences.
    """
    text = canonicalize_query(question).rstrip("?!.")
    for start in _QUESTION_STARTS:
        if text.startswith(start + " "):
            text = text[len(start) + 1 :]
            break
    text = " ".join(text.split())
    if len(text) < 3:
        return text or canonicalize_query(question)
    return text


def _wiki_tries(question: str) -> list[str]:
    """Wikipedia ANDs query words, so shorten from the right until one hits."""
    words = search_keywords(question).split()
    tries = [" ".join(words[:n]) for n in (len(words), 5, 3, 2, 1) if n <= len(words)]
    seen: list[str] = []
    for query in tries:
        if query and query not in seen:
            seen.append(query)
    return seen


def _is_config_error(error: Exception) -> bool:
    """True when retrying is pointless: a key or package is missing."""
    msg = str(error).lower()
    return "is not set" in msg or "is required" in msg


def _is_retryable(error: BaseException) -> bool:
    """Transient failures retry, config errors fail at once."""
    return isinstance(error, _RETRYABLE) and not (
        isinstance(error, Exception) and _is_config_error(error)
    )


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

    async def fetch_one(
        self,
        source: str,
        query: str,
        client: Any = None,
        use_cache: bool = True,
    ) -> list[Source]:
        """Fetch one source with cache, limit, timeout and retries."""
        name = source.strip().lower()
        if name not in ("wikipedia", "arxiv", "web"):
            raise ValueError(f"unknown source: {source!r}")
        if not query.strip():
            return []

        if use_cache:
            hit = self._cache.get(name, f"{_CACHE_VERSION}:{query}")
            if hit is not None:
                logger.info("fetch cache_hit source=%s n=%d", name, len(hit))
                return hit

        await self._limiter.acquire()

        attempts = self._settings.retry_attempts
        last_error: Exception | None = None
        for n in range(1, attempts + 1):
            started = time.monotonic()
            try:
                out = await asyncio.wait_for(
                    self._call_source(name, query, client),
                    timeout=self._settings.per_source_timeout_seconds,
                )
                ms = (time.monotonic() - started) * 1000
                logger.info("fetch ok source=%s n=%d ms=%.0f", name, len(out), ms)
                logger.debug("fetch payload source=%s items=%d", name, len(out))
                if out:
                    self._cache.set(name, f"{_CACHE_VERSION}:{query}", out)
                else:
                    # Never cache an empty hit: with a 24h TTL it would
                    # keep serving "no results" long after the API recovers.
                    logger.info("fetch empty source=%s, not cached", name)
                return out
            except (ValueError, TypeError) as e:
                # programmer error or bad input, retrying will not help
                logger.warning("fetch bad_input source=%s error=%s", name, e)
                raise
            except _RETRYABLE as e:
                last_error = e
                ms = (time.monotonic() - started) * 1000
                if _is_config_error(e):
                    # a missing key never fixes itself, fail at once
                    logger.error("fetch config_error source=%s error=%s", name, e)
                    raise
                logger.warning(
                    "fetch retry source=%s attempt=%d/%d ms=%.0f error=%s",
                    name,
                    n,
                    attempts,
                    ms,
                    e,
                )
                if n < attempts:
                    base = self._settings.retry_min_wait * (2 ** (n - 1))
                    wait = min(self._settings.retry_max_wait, base)
                    wait = wait + random.uniform(0, 0.5)
                    await asyncio.sleep(wait)
        logger.error("fetch failed source=%s error=%s", name, last_error)
        assert last_error is not None
        raise last_error

    async def _call_source(
        self, name: str, query: str, client: Any
    ) -> list[Source]:
        limit = self._settings.max_sources_per_query
        if name == "wikipedia":
            for attempt in _wiki_tries(query):
                logger.debug("wiki try q=%s", attempt[:80])
                out = await _fetch_wikipedia(attempt, max_results=limit, client=client)
                if out:
                    return out
            return []
        if name == "arxiv":
            shaped = search_keywords(query)
            logger.debug("arxiv q=%s", shaped[:80])
            return await _fetch_arxiv(shaped, max_results=limit, client=client)
        logger.debug("web q=%s", canonicalize_query(query)[:80])
        return await _fetch_web(query, max_results=limit, client=client)

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

        attempts = self._settings.retry_attempts

        @retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(
                min=self._settings.retry_min_wait,
                max=self._settings.retry_max_wait,
            ),
            retry=retry_if_exception(_is_retryable),
            reraise=True,
        )
        def _run() -> AnswerWithCitations:
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

        try:
            return _run()
        except _RETRYABLE as e:
            logger.error("synthesize failed error=%s", e)
            raise
