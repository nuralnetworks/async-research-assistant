"""Settings loaded from env."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _HAS_PYDANTIC_SETTINGS = True
except ImportError:
    _HAS_PYDANTIC_SETTINGS = False


def canonicalize_query(q: str) -> str:
    """Lowercase, strip and collapse spaces so cache keys match."""
    return re.sub(r"\s+", " ", q.strip().lower())


if _HAS_PYDANTIC_SETTINGS:

    class _Env(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

        LLM_PROVIDER: str = "gemini"
        LLM_MODEL: str = "gemini-2.0-flash"
        WEB_SEARCH_PROVIDER: str = "duckduckgo"
        LOG_LEVEL: str = "INFO"
        CACHE_DIR: str = "./.cache"
        CACHE_TTL_SECONDS: int = 86400
        PER_SOURCE_TIMEOUT_SECONDS: float = 10.0
        MAX_SOURCES_PER_QUERY: int = 3
        MAX_PARALLEL: int = 5
        RETRY_ATTEMPTS: int = 3
        RETRY_MIN_WAIT: float = 1.0
        RETRY_MAX_WAIT: float = 8.0
        DATABASE_URL: str = "sqlite:///./researcher.db"

else:

    class _Env:
        def __init__(self) -> None:
            import os
            self.LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini")
            self.LLM_MODEL = os.getenv("LLM_MODEL", "gemini-2.0-flash")
            self.WEB_SEARCH_PROVIDER = os.getenv("WEB_SEARCH_PROVIDER", "duckduckgo")
            self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
            self.CACHE_DIR = os.getenv("CACHE_DIR", "./.cache")
            self.CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "86400"))
            self.PER_SOURCE_TIMEOUT_SECONDS = float(os.getenv("PER_SOURCE_TIMEOUT_SECONDS", "10"))
            self.MAX_SOURCES_PER_QUERY = int(os.getenv("MAX_SOURCES_PER_QUERY", "3"))
            self.MAX_PARALLEL = int(os.getenv("MAX_PARALLEL", "5"))
            self.RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))
            self.RETRY_MIN_WAIT = float(os.getenv("RETRY_MIN_WAIT", "1"))
            self.RETRY_MAX_WAIT = float(os.getenv("RETRY_MAX_WAIT", "8"))
            self.DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./researcher.db")


@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    web_search_provider: str
    log_level: str
    cache_dir: Path
    cache_ttl_seconds: int
    per_source_timeout_seconds: float
    max_sources_per_query: int
    max_parallel: int
    retry_attempts: int
    retry_min_wait: float
    retry_max_wait: float
    database_url: str


def get_settings() -> Settings:
    """Read env and return settings."""
    e = _Env()
    provider = str(e.LLM_PROVIDER).lower().strip()
    if provider not in ("anthropic", "openai", "gemini", "google"):
        raise ValueError(f"LLM_PROVIDER must be anthropic|openai|gemini, got {provider!r}")
    wsp = str(e.WEB_SEARCH_PROVIDER).lower().strip()
    if wsp in ("ddg",):
        wsp = "duckduckgo"
    if wsp not in ("tavily", "serper", "duckduckgo"):
        raise ValueError(f"WEB_SEARCH_PROVIDER must be tavily|serper|duckduckgo, got {wsp!r}")
    return Settings(
        llm_provider=provider,
        llm_model=str(e.LLM_MODEL),
        web_search_provider=wsp,
        log_level=str(e.LOG_LEVEL).upper(),
        cache_dir=Path(str(e.CACHE_DIR)),
        cache_ttl_seconds=int(e.CACHE_TTL_SECONDS),
        per_source_timeout_seconds=float(e.PER_SOURCE_TIMEOUT_SECONDS),
        max_sources_per_query=int(e.MAX_SOURCES_PER_QUERY),
        max_parallel=int(e.MAX_PARALLEL),
        retry_attempts=int(e.RETRY_ATTEMPTS),
        retry_min_wait=float(e.RETRY_MIN_WAIT),
        retry_max_wait=float(e.RETRY_MAX_WAIT),
        database_url=str(e.DATABASE_URL),
    )
