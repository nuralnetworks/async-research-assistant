"""Simple token bucket for rate limiting."""

from __future__ import annotations


class TokenBucket:
    """Sleep before external calls when we are over budget."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("rate_limit.py not written yet")
