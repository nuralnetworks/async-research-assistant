"""Request and result models for our code."""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from ai.schemas import Citation, Source

ALLOWED_SOURCES = ("wikipedia", "arxiv", "web")


class ResearchRequest(BaseModel):
    """What the user asked for."""

    question: str
    sources: tuple[str, ...] = ("wikipedia", "arxiv", "web")
    use_cache: bool = True
    max_sources_per_query: int = 3

    @field_validator("question")
    @classmethod
    def _question_length(cls, v: str) -> str:
        text = v.strip()
        if len(text) < 3:
            raise ValueError("question is too short")
        if len(text) > 2000:
            raise ValueError("question is too long (max 2000 chars)")
        return text

    @field_validator("sources")
    @classmethod
    def _sources_known(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for s in v:
            name = s.strip().lower()
            if name == "wiki":
                name = "wikipedia"
            if name not in ALLOWED_SOURCES:
                raise ValueError(f"unknown source: {s!r}")
            if name not in cleaned:
                cleaned.append(name)
        if not cleaned:
            raise ValueError("at least one source is needed")
        return tuple(cleaned)

    @field_validator("max_sources_per_query")
    @classmethod
    def _max_sources_range(cls, v: int) -> int:
        if v < 1 or v > 10:
            raise ValueError("max_sources_per_query must be 1..10")
        return v


class SourceFailure(BaseModel):
    """One source that failed, and why."""

    source: str
    error: str


class ResearchResult(BaseModel):
    """Final answer plus everything the CLI needs to print it."""

    question: str
    answer: str
    citations: list[Citation] = []
    sources: list[Source] = []
    failures: list[SourceFailure] = []
    timings_ms: dict[str, float] = {}
    cache_hit: bool = False
    warnings: list[str] = []
