"""Main flow: validate, fetch, synthesize, save."""

from __future__ import annotations


class ResearchError(RuntimeError):
    """Raised when no source returned anything usable."""


class Researcher:
    """Ties fetch and synthesis together."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("researcher.py not written yet")
