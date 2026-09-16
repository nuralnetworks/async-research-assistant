"""Tests for the command-line interface."""

import sys

import pytest

from researcher.cli import main
from researcher.models import ResearchRequest


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


def test_wiki_alias_maps_to_wikipedia():
    request = ResearchRequest(
        question="What is AI?",
        sources=("wiki",),
    )

    assert request.sources == ("wikipedia",)


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
