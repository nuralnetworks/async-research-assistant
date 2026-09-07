"""Benchmark sequential and parallel source fetching.

Examples:
    python scripts/bench.py
    python scripts/bench.py --offline
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.schemas import Source
from researcher.concurrency.orchestrator import FetchOutcome, fetch_all
from researcher.config import Settings, get_settings
from researcher.models import SourceFailure
from researcher.storage.cache_store import SqliteCacheStore


QUESTION_FILE = PROJECT_ROOT / "data" / "research_questions.json"
RESULT_FILE = PROJECT_ROOT / "bench_result.md"
SOURCE_NAMES = ("wikipedia", "arxiv", "web")
SIMULATED_IO_SECONDS = 0.300
QUESTION_LIMIT = 5


class DelayedOfflineService:
    """Simulate source I/O without using the network."""

    def __init__(self, delay_seconds: float) -> None:
        self._delay_seconds = delay_seconds

    async def fetch_one(
        self,
        source: str,
        query: str,
        client: Any = None,
    ) -> list[Source]:
        """Wait for the configured delay and return a fake source."""
        del client

        await asyncio.sleep(self._delay_seconds)

        return [
            Source(
                title=f"Benchmark {source} result",
                url=(
                    f"https://example.test/benchmark/{source}/"
                    f"{abs(hash(query))}"
                ),
                snippet=f"Simulated result for: {query}",
                origin=source,
            )
        ]


def parse_args() -> argparse.Namespace:
    """Parse benchmark arguments."""
    parser = argparse.ArgumentParser(
        description="Compare sequential and parallel source fetching.",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help=(
            "Run without network access. The benchmark is always simulated "
            "and therefore offline-safe."
        ),
    )
    return parser.parse_args()


def load_questions() -> list[str]:
    """Read up to five questions from the data file."""
    payload = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    raw_questions = payload.get("questions")

    if not isinstance(raw_questions, list):
        raise ValueError("research_questions.json must contain a questions list")

    questions = [
        str(item.get("text", "")).strip()
        for item in raw_questions[:QUESTION_LIMIT]
    ]

    if not questions or any(not question for question in questions):
        raise ValueError("the benchmark requires five non-empty questions")

    return questions


async def fetch_sequential(
    question: str,
    settings: Settings,
    service: DelayedOfflineService,
) -> FetchOutcome:
    """Fetch each source one after another."""
    collected_sources: list[Source] = []
    failures: list[SourceFailure] = []
    timings_ms: dict[str, float] = {}

    for source_name in SOURCE_NAMES:
        started = time.perf_counter()

        try:
            sources = await service.fetch_one(source_name, question)
        except Exception as error:
            failures.append(
                SourceFailure(
                    source=source_name,
                    error=str(error),
                )
            )
        else:
            collected_sources.extend(sources)
        finally:
            timings_ms[source_name] = round(
                (time.perf_counter() - started) * 1000,
                1,
            )

    return FetchOutcome(
        sources=collected_sources,
        failures=failures,
        timings_ms=timings_ms,
    )


async def benchmark_sequential(
    questions: list[str],
    settings: Settings,
) -> tuple[float, int]:
    """Benchmark sequential fetching across all questions."""
    service = DelayedOfflineService(SIMULATED_IO_SECONDS)
    source_count = 0
    started = time.perf_counter()

    for question in questions:
        outcome = await fetch_sequential(question, settings, service)
        source_count += len(outcome.sources)

    duration = time.perf_counter() - started
    return duration, source_count


async def benchmark_parallel(
    questions: list[str],
    settings: Settings,
) -> tuple[float, int]:
    """Benchmark fetch_all across all questions."""
    service = DelayedOfflineService(SIMULATED_IO_SECONDS)
    source_count = 0
    started = time.perf_counter()

    for question in questions:
        outcome = await fetch_all(
            question,
            SOURCE_NAMES,
            settings,
            service,
        )
        source_count += len(outcome.sources)

    duration = time.perf_counter() - started
    return duration, source_count


def device_details() -> dict[str, str]:
    """Collect reproducibility information for the report."""
    processor = platform.processor().strip() or "Not reported by OS"

    return {
        "Operating system": platform.platform(),
        "Machine": platform.machine() or "Unknown",
        "Processor": processor,
        "Logical CPU count": str(os.cpu_count() or "Unknown"),
        "Python version": platform.python_version(),
        "Python implementation": platform.python_implementation(),
    }


def format_terminal_table(
    sequential_seconds: float,
    parallel_seconds: float,
    sequential_sources: int,
    parallel_sources: int,
) -> str:
    """Create a fixed-width terminal table."""
    speedup = sequential_seconds / parallel_seconds

    header = (
        f"{'Mode':<14}"
        f"{'Duration (s)':>15}"
        f"{'Sources':>12}"
        f"{'Speedup':>12}"
    )
    separator = "-" * len(header)

    return "\n".join(
        [
            header,
            separator,
            (
                f"{'Sequential':<14}"
                f"{sequential_seconds:>15.3f}"
                f"{sequential_sources:>12}"
                f"{'1.00x':>12}"
            ),
            (
                f"{'Parallel':<14}"
                f"{parallel_seconds:>15.3f}"
                f"{parallel_sources:>12}"
                f"{f'{speedup:.2f}x':>12}"
            ),
        ]
    )


def save_markdown_report(
    sequential_seconds: float,
    parallel_seconds: float,
    sequential_sources: int,
    parallel_sources: int,
    question_count: int,
) -> None:
    """Save benchmark results and environment details."""
    speedup = sequential_seconds / parallel_seconds
    details = device_details()

    lines = [
        "# Benchmark Result",
        "",
        "## Method",
        "",
        f"- Questions: {question_count}",
        f"- Sources per question: {len(SOURCE_NAMES)}",
        f"- Simulated I/O delay per source: {SIMULATED_IO_SECONDS * 1000:.0f} ms",
        "- Cache cleared before execution: yes",
        "- Network access: none",
        "",
        "## Results",
        "",
        "| Mode | Duration (s) | Sources fetched | Relative speed |",
        "|---|---:|---:|---:|",
        (
            f"| Sequential | {sequential_seconds:.3f} | "
            f"{sequential_sources} | 1.00x |"
        ),
        (
            f"| Parallel (`fetch_all`) | {parallel_seconds:.3f} | "
            f"{parallel_sources} | {speedup:.2f}x |"
        ),
        "",
        "## Device and Runtime",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]

    for name, value in details.items():
        escaped_value = value.replace("|", "\\|")
        lines.append(f"| {name} | {escaped_value} |")

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            (
                "Each question performs three independent simulated I/O "
                "operations. Sequential execution waits for all three delays, "
                "whereas `fetch_all` overlaps them. A speedup close to 3x is "
                "therefore expected."
            ),
            "",
        ]
    )

    RESULT_FILE.write_text("\n".join(lines), encoding="utf-8")


async def run_benchmark() -> None:
    """Clear cache, execute both benchmarks, and save the report."""
    questions = load_questions()
    settings = replace(
        get_settings(),
        max_parallel=3,
        per_source_timeout_seconds=2.0,
    )

    cache = SqliteCacheStore(settings)

    try:
        cache.clear()

        sequential_seconds, sequential_sources = (
            await benchmark_sequential(questions, settings)
        )

        parallel_seconds, parallel_sources = await benchmark_parallel(
            questions,
            settings,
        )
    finally:
        cache.close()

    table = format_terminal_table(
        sequential_seconds,
        parallel_seconds,
        sequential_sources,
        parallel_sources,
    )

    print("Async Research Assistant Benchmark")
    print()
    print(table)
    print()
    print(f"Questions: {len(questions)}")
    print(f"Simulated source delay: {SIMULATED_IO_SECONDS * 1000:.0f} ms")
    print(f"Python: {platform.python_version()}")

    save_markdown_report(
        sequential_seconds,
        parallel_seconds,
        sequential_sources,
        parallel_sources,
        len(questions),
    )

    print(f"Saved report: {RESULT_FILE}")


def main() -> None:
    """Run the benchmark."""
    parse_args()

    try:
        asyncio.run(run_benchmark())
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"Benchmark error: {error}", file=sys.stderr)
        raise SystemExit(2) from error


if __name__ == "__main__":
    main()