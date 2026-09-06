"""Small rate limiter used before external calls."""

from __future__ import annotations

import abc
import asyncio
import time


class RateLimiter(abc.ABC):
    """Base class so we can swap the real limiter for a no-op in tests."""

    @abc.abstractmethod
    async def acquire(self) -> None:
        """Wait until we are allowed to make one call."""
        raise NotImplementedError


class NoopLimiter(RateLimiter):
    """Does nothing. Used in offline mode and unit tests."""

    async def acquire(self) -> None:
        return None


class TokenBucket(RateLimiter):
    """Classic token bucket.

    We add `rate_per_sec` tokens every second, up to `capacity`.
    Each call takes one token. If no token is left, we sleep
    until one is available.
    """

    def __init__(self, rate_per_sec: float, capacity: int) -> None:
        if rate_per_sec <= 0:
            raise ValueError("rate_per_sec must be positive")
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        self._rate = float(rate_per_sec)
        self._capacity = int(capacity)
        self._tokens = float(capacity)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self, now: float) -> None:
        passed = now - self._updated
        if passed > 0:
            self._tokens = min(self._capacity, self._tokens + passed * self._rate)
            self._updated = now

    async def acquire(self) -> None:
        while True:
            async with self._lock:
                now = time.monotonic()
                self._refill(now)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return None
                missing = 1.0 - self._tokens
                wait = missing / self._rate
            await asyncio.sleep(wait)
