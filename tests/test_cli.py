"""Tests for the command-line interface."""

import asyncio
import json
import sys

import pytest

from ai.schemas import Citation, Source
from researcher.cli import OfflineService, main, render_result
from researcher.models import ResearchResult


@pytest.fixture(autouse=True)
def fake_researcher(monkeypatch):
    """CLI unit tests depend on the frozen contract, not the real core."""
    requests = []

    class FakeResearcher:
        def __init__(self, settings, service):
            pass

        async def ask(self, request):
            requests.append(request)
            source = Source(
                title="Photosynthesis",
                url="https://en.wikipedia.org/wiki/Photosynthesis",
                origin="wikipedia", snippet="Canned test reference",
            )
            return ResearchResult(
                question=request.question, answer="Example answer [1]",
                citations=[Citation(index=1, source=source)], sources=[source],
                timings_ms={"wikipedia": 1.5},
            )

    monkeypatch.setattr("researcher.cli.Researcher", FakeResearcher)
    return requests


def test_json_output_matches_flattened_contract(capsys):
    main(["ask", "What is AI?", "--offline", "--json"])
    result = json.loads(capsys.readouterr().out)
    assert set(result) == {"question", "answer", "citations", "timings_ms"}
    assert result["timings_ms"] == {"wikipedia": 1.5}
    assert result["citations"][0] == {
        "index": 1, "title": "Photosynthesis", "origin": "wikipedia",
        "url": "https://en.wikipedia.org/wiki/Photosynthesis",
    }


def test_warning_output_only_when_present(capsys):
    result = ResearchResult(question="What is AI?", answer="Example [1]")
    render_result(result)
    assert "Warnings:" not in capsys.readouterr().out
    result.warnings = ["arxiv unavailable", "using remaining sources"]
    render_result(result)
    assert capsys.readouterr().out.endswith(
        "Warnings: arxiv unavailable; using remaining sources\n"
    )


@pytest.mark.parametrize("question", ["What is photosynthesis?", "What is AI?"])
def test_offline_service_uses_canned_sources_only(question, monkeypatch):
    def forbidden_network(*args, **kwargs):
        pytest.fail("offline service attempted network access")

    monkeypatch.setattr("httpx.AsyncClient.request", forbidden_network)
    monkeypatch.setattr("httpx.Client.request", forbidden_network)
    service = OfflineService()
    sources = []
    for name in ("wikipedia", "arxiv", "web"):
        fetched = asyncio.run(service.fetch_one(name, question))
        assert [source.origin for source in fetched] == [name]
        sources.extend(fetched)
    answer = service.synthesize(question, sources)
    assert "fake LLM" in answer.answer
    assert [citation.index for citation in answer.citations] == [1, 2, 3]
    assert sources[1].url.startswith("https://example.test/")


def test_online_no_cache_never_opens_database(monkeypatch, capsys):
    def forbidden_store(*args):
        pytest.fail("--no-cache must not open persistent storage")

    class FakeService:
        def __init__(self, settings, cache, limiter):
            self.cache = cache

        async def fetch_one(self, source, query, client=None, use_cache=True):
            assert use_cache is False
            self.cache.set(source, query, [])
            assert self.cache.get(source, query) is None
            return []

    class FakeResearcher:
        def __init__(self, settings, service):
            self.service = service

        async def ask(self, request):
            assert request.use_cache is False
            assert request.sources == ("wikipedia", "arxiv")
            await self.service.fetch_one("wikipedia", request.question)
            return ResearchResult(question=request.question, answer="Example")

    monkeypatch.setattr("researcher.cli.SqliteCacheStore", forbidden_store)
    monkeypatch.setattr("researcher.cli.ResilientAIService", FakeService)
    monkeypatch.setattr("researcher.cli.Researcher", FakeResearcher)
    main(["ask", "What is AI?", "--sources", "wiki,arxiv", "--no-cache"])
    assert "A: Example" in capsys.readouterr().out


@pytest.mark.parametrize("fails", [False, True])
def test_cache_closes_after_research(monkeypatch, capsys, fails):
    from researcher.core.researcher import ResearchError

    closed = []

    class FakeStore:
        def __init__(self, settings):
            pass

        def close(self):
            closed.append(True)

    class FakeResearcher:
        def __init__(self, settings, service):
            pass

        async def ask(self, request):
            if fails:
                raise ResearchError("all sources unavailable")
            return ResearchResult(question=request.question, answer="Example")

    monkeypatch.setattr("researcher.cli.SqliteCacheStore", FakeStore)
    monkeypatch.setattr("researcher.cli.Researcher", FakeResearcher)
    if fails:
        with pytest.raises(SystemExit) as exc:
            main(["ask", "What is AI?"])
        assert exc.value.code == 1
        error = capsys.readouterr().err
        assert "all sources unavailable" in error
        assert "Traceback" not in error
    else:
        main(["ask", "What is AI?"])
    assert closed == [True]


def test_no_cache_store_never_reads_or_writes():
    from researcher.cli import NoCacheStore

    store = NoCacheStore()
    store.set("wikipedia", "What is AI?", [])
    store.clear()
    assert store.get("wikipedia", "What is AI?") is None


@pytest.mark.parametrize("question", ["", "  ", "a", "x" * 2001])
def test_question_boundaries(question, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["ask", question, "--offline"])
    assert exc.value.code == 2
    assert "question must be between 3 and 2000 characters" in capsys.readouterr().err


@pytest.mark.parametrize("sources", ["", ",", "wiki,youtube"])
def test_invalid_sources(sources, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["ask", "What is AI?", "--sources", sources])
    assert exc.value.code == 2
    error = capsys.readouterr().err
    assert "--sources must be" in error
    assert "Traceback" not in error


@pytest.mark.parametrize("limit", ["0", "11", "abc"])
def test_invalid_source_limit(limit, capsys):
    with pytest.raises(SystemExit) as exc:
        main(["ask", "What is AI?", "--max-sources", limit])
    assert exc.value.code == 2
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("flags", [[], ["--offline"]])
def test_benchmark_dispatch(flags, monkeypatch):
    calls = []

    async def fake_benchmark():
        calls.append(True)

    monkeypatch.setattr("researcher.cli.run_benchmark", fake_benchmark)
    main(["bench", *flags])
    assert calls == [True]


def test_demo_dispatch(monkeypatch):
    calls = []

    async def fake_demo(limit, offline):
        calls.append((limit, offline))
        return 0

    monkeypatch.setattr("researcher.cli.run_demo", fake_demo)
    main(["demo", "--offline", "--limit", "2"])
    assert calls == [(2, True)]


def test_wiki_alias_maps_to_wikipedia(fake_researcher):
    main(["ask", "What is AI?", "--sources", "wiki,arxiv", "--offline"])
    assert fake_researcher[0].sources == ("wikipedia", "arxiv")


def test_invalid_source_exits_with_code_2(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "researcher",
            "ask",
            "What is AI?",
            "--sources",
            "youtube",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2

    captured = capsys.readouterr()

    assert "--sources must be one or more of: wiki, arxiv, web" in captured.err
    assert "Traceback" not in captured.err


def test_short_question_exits_with_code_2(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "researcher",
            "ask",
            "a",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 2

    captured = capsys.readouterr()

    assert "question must be between 3 and 2000 characters" in captured.err
    assert "Traceback" not in captured.err


def test_offline_output_contains_citation_and_url(monkeypatch, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "researcher",
            "ask",
            "What is photosynthesis?",
            "--offline",
            "--sources",
            "wiki",
        ],
    )

    main()

    captured = capsys.readouterr()

    assert "[1]" in captured.out
    assert "https://en.wikipedia.org/wiki/Photosynthesis" in captured.out
    assert "References:" in captured.out


def test_offline_mode_does_not_need_api_keys(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "researcher",
            "ask",
            "What is AI?",
            "--offline",
        ],
    )

    main()

    captured = capsys.readouterr()

    assert "Q: What is AI?" in captured.out
    assert "References:" in captured.out
    assert "Traceback" not in captured.err


def test_no_cache_sets_use_cache_false(monkeypatch, capsys):
    captured_request = {}

    class FakeResearcher:
        def __init__(self, settings, service):
            pass

        async def ask(self, request):
            captured_request["request"] = request

            class FakeResult:
                def __init__(self):
                    self.question = request.question
                    self.answer = "Fake answer [1]"
                    self.citations = []
                    self.warnings = []
                    self.timings_ms = {}

            return FakeResult()

    monkeypatch.setattr(
        "researcher.cli.Researcher",
        FakeResearcher,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "researcher",
            "ask",
            "What is AI?",
            "--offline",
            "--no-cache",
        ],
    )

    main()

    assert captured_request["request"].use_cache is False
