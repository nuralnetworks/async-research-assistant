from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ai.schemas import AnswerWithCitations, Citation, Source
from researcher.config import Settings, get_settings
from researcher.core.researcher import ResearchError, Researcher
from researcher.models import ResearchRequest, ResearchResult
from researcher.services.ai_service import ResilientAIService
from researcher.services.rate_limit import NoopLimiter, TokenBucket
from researcher.storage.cache_store import SqliteCacheStore


QUESTION_FILE = PROJECT_ROOT / "data" / "research_questions.json"
ARTEFACTS_DIR = PROJECT_ROOT / "artefacts"
ANSWERS_FILE = ARTEFACTS_DIR / "answers.json"


class OfflineAIService:
    def __init__(self, cache: SqliteCacheStore) -> None:
        self._cache = cache

    async def fetch_one(
        self,
        source: str,
        query: str,
        client: Any = None,
        use_cache: bool = True,
    ) -> list[Source]:

        del client

        if use_cache:
            cached = self._cache.get(source, query)
            if cached is not None:
                return cached

        source_names = {
            "wikipedia": "Offline Encyclopedia",
            "arxiv": "Offline Research Paper",
            "web": "Offline Technical Guide",
        }

        source_urls = {
            "wikipedia": "https://example.test/offline/wikipedia",
            "arxiv": "https://example.test/offline/arxiv",
            "web": "https://example.test/offline/web",
        }

        result = [
            Source(
                title=f"{source_names[source]}: {query}",
                url=f"{source_urls[source]}/{abs(hash(query))}",
                snippet=(
                    f"This offline {source} reference contains background "
                    f"information relevant to the question: {query}"
                ),
                origin=source,
            )
        ]

        self._cache.set(source, query, result)
        return result

    def synthesize(
        self,
        question: str,
        sources: list[Source],
    ) -> AnswerWithCitations:
        if not question.strip():
            raise ValueError("question must not be blank")
        if not sources:
            raise ValueError("sources must not be empty")

        citation_count = min(3, len(sources))
        markers = " ".join(f"[{index}]" for index in range(1, citation_count + 1))

        answer = (
            f"The available offline references provide an overview of "
            f"“{question}” {markers}. This answer was generated in offline mode, "
            f"so it demonstrates the complete research pipeline without making "
            f"network or external LLM requests [1]."
        )

        citations = [
            Citation(index=index, source=sources[index - 1])
            for index in range(1, citation_count + 1)
        ]

        return AnswerWithCitations(
            question=question,
            answer=answer,
            citations=citations,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the sample research questions.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum number of questions to process (default: 5).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use deterministic local providers with no network access.",
    )
    return parser.parse_args()


def load_questions(limit: int) -> list[dict[str, Any]]:
    if limit < 1:
        raise ValueError("--limit must be at least 1")

    if not QUESTION_FILE.is_file():
        raise FileNotFoundError(f"question file not found: {QUESTION_FILE}")

    payload = json.loads(QUESTION_FILE.read_text(encoding="utf-8"))
    questions = payload.get("questions")

    if not isinstance(questions, list):
        raise ValueError("research_questions.json must contain a questions list")

    return questions[:limit]


def build_researcher(
    settings: Settings,
    cache: SqliteCacheStore,
    offline: bool,
) -> Researcher:
    if offline:
        service: Any = OfflineAIService(cache)
    else:
        limiter = TokenBucket(
            rate_per_sec=max(1.0, float(settings.max_parallel)),
            capacity=max(1, settings.max_parallel),
        )
        service = ResilientAIService(settings, cache, limiter)

    return Researcher(settings, service)


def result_to_json(
    question_data: dict[str, Any],
    result: ResearchResult,
) -> dict[str, Any]:
    return {
        "id": question_data.get("id"),
        "difficulty": question_data.get("difficulty"),
        "question": result.question,
        "answer": result.answer,
        "citations": [
            {
                "index": citation.index,
                "title": citation.source.title,
                "url": citation.source.url,
                "origin": citation.source.origin,
            }
            for citation in result.citations
        ],
        "sources": [
            {
                "title": source.title,
                "url": source.url,
                "snippet": source.snippet,
                "origin": source.origin,
            }
            for source in result.sources
        ],
        "failures": [
            {
                "source": failure.source,
                "error": failure.error,
            }
            for failure in result.failures
        ],
        "timings_ms": result.timings_ms,
        "cache_hit": result.cache_hit,
        "warnings": result.warnings,
    }


def render_digest(results: list[dict[str, Any]], offline: bool) -> str:
    today = date.today().isoformat()
    mode = "offline" if offline else "live"

    lines = [
        f"# Research Digest — {today}",
        "",
        f"- Mode: **{mode}**",
        f"- Questions processed: **{len(results)}**",
        "",
    ]

    for number, item in enumerate(results, start=1):
        lines.extend(
            [
                f"## {number}. {item['question']}",
                "",
                item["answer"],
                "",
            ]
        )

        if item["sources"]:
            lines.append("### Sources")
            lines.append("")

            for source_number, source in enumerate(item["sources"], start=1):
                lines.append(
                    f"{source_number}. **{source['title']}** "
                    f"({source['origin']}) — {source['url']}"
                )

            lines.append("")

        if item["warnings"]:
            lines.append("### Warnings")
            lines.append("")

            for warning in item["warnings"]:
                lines.append(f"- {warning}")

            lines.append("")

        timings = item["timings_ms"]
        if timings:
            formatted = ", ".join(
                f"{source}: {duration:.1f} ms"
                for source, duration in timings.items()
            )
            lines.extend(
                [
                    f"**Fetch timings:** {formatted}",
                    "",
                ]
            )

    return "\n".join(lines).rstrip() + "\n"


def save_artefacts(
    results: list[dict[str, Any]],
    offline: bool,
) -> tuple[Path, Path]:
    ARTEFACTS_DIR.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_on": date.today().isoformat(),
        "offline": offline,
        "count": len(results),
        "results": results,
    }

    ANSWERS_FILE.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    digest_file = ARTEFACTS_DIR / f"digest-{date.today().isoformat()}.md"
    digest_file.write_text(
        render_digest(results, offline),
        encoding="utf-8",
    )

    return ANSWERS_FILE, digest_file


async def run_demo(limit: int, offline: bool) -> int:
    settings = get_settings()
    questions = load_questions(limit)
    cache = SqliteCacheStore(settings)
    researcher = build_researcher(settings, cache, offline)

    completed: list[dict[str, Any]] = []

    try:
        for number, question_data in enumerate(questions, start=1):
            question = str(question_data.get("text", "")).strip()

            requested_sources = tuple(
                question_data.get("expected_sources")
                or ("wikipedia", "arxiv", "web")
            )

            request = ResearchRequest(
                question=question,
                sources=requested_sources,
                use_cache=True,
                max_sources_per_query=min(
                    len(requested_sources),
                    settings.max_sources_per_query,
                ),
            )

            print(f"[{number}/{len(questions)}] {question}")

            try:
                result = await researcher.ask(request)
            except ResearchError as error:
                print(f"  Research failed: {error}", file=sys.stderr)
                continue

            completed.append(result_to_json(question_data, result))

            print(f"  Answer: {result.answer}")
            print(f"  Sources: {len(result.sources)}")

            for warning in result.warnings:
                print(f"  Warning: {warning}")

            print()

        answers_file, digest_file = save_artefacts(completed, offline)

        print(f"Saved JSON: {answers_file}")
        print(f"Saved digest: {digest_file}")

        return 0 if completed else 1
    finally:
        cache.close()


def main() -> None:
    args = parse_args()

    try:
        exit_code = asyncio.run(
            run_demo(limit=args.limit, offline=args.offline)
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        print(f"Demo error: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()