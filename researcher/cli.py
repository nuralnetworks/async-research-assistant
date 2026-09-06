"""Command line interface.

Handles:
  python -m researcher ask "question" [--sources wiki,arxiv,web] [--no-cache] [--json] [--offline]
  python -m researcher demo [--limit 5] [--offline]
  python -m researcher bench [--offline]
"""

from __future__ import annotations


def main() -> None:
    """Parse args and print the answer with references."""
    raise NotImplementedError("cli.py not written yet")
