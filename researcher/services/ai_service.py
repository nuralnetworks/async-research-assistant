"""Wraps ai calls with retries, timeouts and logging."""

from __future__ import annotations


class ResilientAIService:
    """All ai access goes through here."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("ai_service.py not written yet")
