"""Fetches the three sources together."""

from __future__ import annotations


class FetchOutcome:
    """What came back: sources, failures and per source timings."""

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError("orchestrator.py not written yet")


async def fetch_all(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Run all sources with timeouts, one failure does not stop the rest."""
    raise NotImplementedError("orchestrator.py not written yet")
