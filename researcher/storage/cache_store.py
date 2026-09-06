"""Cache for (source, query) pairs with TTL."""

from __future__ import annotations


class CacheStore:
    """Base cache. SQLite is the main one, files are the fallback."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("cache_store.py not written yet")
