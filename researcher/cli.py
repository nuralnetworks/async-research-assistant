"""Command line interface for the research assistant."""

from __future__ import annotations

import argparse
import asyncio
import json

from pydantic import ValidationError

from ai.schemas import AnswerWithCitations, Citation, Source
from researcher.config import get_settings
from researcher.core.researcher import Researcher
from researcher.models import ResearchRequest
from researcher.services.ai_service import ResilientAIService
from researcher.services.rate_limit import TokenBucket
from researcher.storage.cache_store import CacheStore, SqliteCacheStore
from scripts.bench import run_benchmark
from scripts.demo import run_demo


class OfflineService:
    """Fake research service for offline CLI mode."""

    async def fetch_one(
        self,
        source: str,
        query: str,
        client=None,
    ) -> list[Source]:
        """Return canned sources without using the network."""

        if "photosynthesis" in query.lower():
            sources = [
                Source(
                    title="Photosynthesis",
                    url="https://en.wikipedia.org/wiki/Photosynthesis",
                    snippet=(
                        "Photosynthesis is a process used by plants and other "
                        "organisms to convert light energy into chemical energy."
                    ),
                    origin="wikipedia",
                ),
                Source(
                    title="Light-Dependent Reactions of Photosynthesis",
                    url="https://arxiv.org/abs/1706.03762",
                    snippet=(
                        "A review of the light-dependent reactions of "
                        "photosynthesis."
                    ),
                    origin="arxiv",
                ),
                Source(
                    title="How Plants Make Food",
                    url="https://example.com/plants",
                    snippet=(
                        "Plants use chlorophyll to absorb sunlight and "
                        "produce glucose."
                    ),
                    origin="web",
                ),
            ]

            return [
                item
                for item in sources
                if item.origin == source
            ]

        return [
            Source(
                title=f"Offline {source} reference",
                url=f"https://example.com/{source}",
                snippet=f"Offline reference for: {query}",
                origin=source,
            )
        ]

    def synthesize(
        self,
        question: str,
        sources: list[Source],
    ) -> AnswerWithCitations:
        """Create a fake cited answer from offline sources."""

        citations = [
            Citation(
                index=index,
                source=source,
            )
            for index, source in enumerate(sources, start=1)
        ]

        markers = " ".join(
            f"[{citation.index}]"
            for citation in citations
        )

        answer = (
            "Based on the available offline sources, "
            f"the main information is supported by {markers}."
        )

        return AnswerWithCitations(
            question=question,
            answer=answer,
            citations=citations,
        )


def build_parser() -> argparse.ArgumentParser:
    """Create and configure the command-line argument parser."""

    parser = argparse.ArgumentParser(
        prog="researcher",
        description="Async Research Assistant",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    ask_parser = subparsers.add_parser(
        "ask",
        help="Ask a research question",
    )

    ask_parser.add_argument(
        "question",
        help="Research question",
    )

    ask_parser.add_argument(
        "--sources",
        default="wiki,arxiv,web",
        help="Comma-separated sources: wiki, arxiv, web",
    )

    ask_parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not use cached results",
    )

    ask_parser.add_argument(
        "--json",
        action="store_true",
        help="Print result as JSON",
    )

    ask_parser.add_argument(
        "--offline",
        action="store_true",
        help="Use canned sources and fake LLM without network",
    )

    ask_parser.add_argument(
        "--max-sources",
        type=int,
        default=3,
        help="Maximum number of sources per query",
    )

    demo_parser = subparsers.add_parser(
        "demo",
        help="Run sample research questions",
    )

    demo_parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of questions to process",
    )

    demo_parser.add_argument(
        "--offline",
        action="store_true",
        help="Run demo without network access",
    )

    subparsers.add_parser(
        "bench",
        help="Run sequential vs parallel benchmark",
    )

    return parser


def render_result(result) -> None:
    """Print a research result in human-readable format."""

    print(f"Q: {result.question}")
    print()
    print(f"A: {result.answer}")
    print()

    if result.citations:
        print("References:")

        for citation in result.citations:
            print(
                f"  [{citation.index}] "
                f"({citation.source.origin}) "
                f"{citation.source.title}"
            )
            print(f"      {citation.source.url}")

    if result.warnings:
        print()
        print(f"Warnings: {'; '.join(result.warnings)}")


def render_json(result) -> None:
    """Print a research result as JSON."""

    answer = AnswerWithCitations(
        question=result.question,
        answer=result.answer,
        citations=result.citations,
    )

    output = answer.to_dict()
    output["timings_ms"] = result.timings_ms

    print(
        json.dumps(
            output,
            indent=2,
            ensure_ascii=False,
        )
    )

class NoCacheStore(CacheStore):
    """Cache implementation that never reads or writes data."""

    def get(self, source: str, query: str) -> list[Source] | None:
        return None

    def set(
        self,
        source: str,
        query: str,
        value: list[Source],
    ) -> None:
        pass

    def clear(self) -> None:
        pass


class CacheAwareService:
    """Pass the CLI cache preference to the real AI service."""

    def __init__(
        self,
        service: ResilientAIService,
        use_cache: bool,
    ) -> None:
        self._service = service
        self._use_cache = use_cache

    async def fetch_one(
        self,
        source: str,
        query: str,
        client=None,
    ) -> list[Source]:
        return await self._service.fetch_one(
            source,
            query,
            client=client,
            use_cache=self._use_cache,
        )

    def synthesize(
        self,
        question: str,
        sources: list[Source],
    ) -> AnswerWithCitations:
        return self._service.synthesize(
            question,
            sources,
        )


def main() -> None:
    """Parse command-line arguments and run the selected command."""

    parser = build_parser()
    args = parser.parse_args()

    if args.command == "ask":
        sources = tuple(
            source.strip()
            for source in args.sources.split(",")
            if source.strip()
        )

        try:
            request = ResearchRequest(
                question=args.question,
                sources=sources,
                use_cache=not args.no_cache,
                max_sources_per_query=args.max_sources,
            )

        except ValidationError as exc:
            field = exc.errors()[0]["loc"][0]

            if field == "sources":
                parser.error(
                    "--sources must be one or more of: wiki, arxiv, web"
                )

            elif field == "question":
                parser.error(
                    "question must be between 3 and 2000 characters"
                )

            elif field == "max_sources_per_query":
                parser.error(
                    "--max-sources must be between 1 and 10"
                )

            else:
                parser.error("invalid research request")

        if args.offline:
            settings = get_settings()

            offline_service = OfflineService()

            researcher = Researcher(
                settings,
                offline_service,
            )

            result = asyncio.run(
                researcher.ask(request)
            )

            if args.json:
                render_json(result)
            else:
                render_result(result)

        else:
            settings = get_settings()

            cache = SqliteCacheStore(settings)

            service_cache: CacheStore

            if request.use_cache:
                service_cache = cache
            else:
                service_cache = NoCacheStore()

            limiter = TokenBucket(
                rate_per_sec=max(
                    1.0,
                    float(settings.max_parallel),
                ),
                capacity=max(
                    1,
                    settings.max_parallel,
                ),
            )

            real_service = ResilientAIService(
                settings,
                service_cache,
                limiter,
            )

            online_service = CacheAwareService(
                real_service,
                use_cache=request.use_cache,
            )

            researcher = Researcher(
                settings,
                online_service,
            )

            try:
                result = asyncio.run(
                    researcher.ask(request)
                )

                if args.json:
                    render_json(result)
                else:
                    render_result(result)

            finally:
                cache.close()

    elif args.command == "demo":
        try:
            exit_code = asyncio.run(
                run_demo(
                    limit=args.limit,
                    offline=args.offline,
                )
            )

        except (
            FileNotFoundError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            parser.error(str(error))

        if exit_code != 0:
            raise SystemExit(exit_code)

    elif args.command == "bench":
        try:
            asyncio.run(
                run_benchmark()
            )

        except (
            FileNotFoundError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            parser.error(str(error))

def test_no_cache_store_never_reads_or_writes():
    from researcher.cli import NoCacheStore

    store = NoCacheStore()

    assert store.get("wikipedia", "What is AI?") is None

    store.set(
        "wikipedia",
        "What is AI?",
        [],
    )

    store.clear()

    assert store.get("wikipedia", "What is AI?") is None