"""Logging setup.

Usage:
    from researcher.logging_setup import setup_logging
    setup_logging("INFO")
"""

from __future__ import annotations

import logging
import os


def setup_logging(level: str | None = None) -> None:
    """Set up stdlib logging from arg or LOG_LEVEL."""
    resolved: str = level or os.getenv("LOG_LEVEL") or "INFO"
    lvl = resolved.upper()
    logging.basicConfig(
        level=getattr(logging, lvl, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
