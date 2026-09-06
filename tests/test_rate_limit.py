"""Tests for the token bucket limiter."""

from __future__ import annotations

import time

import pytest

from researcher.services.rate_limit import NoopLimiter, TokenBucket


@pytest.mark.asyncio
async def test_first_calls_go_through() -> None:
    bucket = TokenBucket(rate_per_sec=10, capacity=3)
    started = time.monotonic()
    await bucket.acquire()
    await bucket.acquire()
    await bucket.acquire()
    assert time.monotonic() - started < 1.0


@pytest.mark.asyncio
async def test_over_capacity_waits() -> None:
    bucket = TokenBucket(rate_per_sec=20, capacity=1)
    await bucket.acquire()
    started = time.monotonic()
    await bucket.acquire()
    waited = time.monotonic() - started
    # one token at 20/sec takes about 0.05s to refill
    assert waited >= 0.03


@pytest.mark.asyncio
async def test_noop_never_waits() -> None:
    limiter = NoopLimiter()
    started = time.monotonic()
    for _ in range(5):
        await limiter.acquire()
    assert time.monotonic() - started < 1.0


def test_bad_args_rejected() -> None:
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=0, capacity=1)
    with pytest.raises(ValueError):
        TokenBucket(rate_per_sec=1, capacity=0)
