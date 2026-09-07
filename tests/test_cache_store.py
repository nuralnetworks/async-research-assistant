import time
from pathlib import Path

import pytest

from ai.schemas import Source
from researcher.config import Settings
from researcher.storage.cache_store import SqliteCacheStore, FileJsonCacheStore


def _source(title="T", url="https://example.com", origin="wikipedia"):
    return Source(title=title, url=url, snippet="snippet", origin=origin)


def _settings(tmp_path, ttl=86400):
    return Settings(
        llm_provider="anthropic",
        llm_model="claude-sonnet-4-6",
        web_search_provider="duckduckgo",
        log_level="INFO",
        cache_dir=Path(tmp_path / "filecache"),
        cache_ttl_seconds=ttl,
        per_source_timeout_seconds=10.0,
        max_sources_per_query=3,
        max_parallel=5,
        retry_attempts=3,
        retry_min_wait=1.0,
        retry_max_wait=8.0,
        database_url=f"sqlite:///{tmp_path / 'cache.db'}",
    )


@pytest.mark.parametrize("store_cls", [SqliteCacheStore, FileJsonCacheStore])
def test_roundtrip(tmp_path, store_cls):
    store = store_cls(_settings(tmp_path))
    assert store.get("wikipedia", "what is X?") is None

    value = [_source(title="A"), _source(title="B", origin="arxiv")]
    store.set("wikipedia", "what is X?", value)
    got = store.get("wikipedia", "what is X?")

    assert got is not None
    assert [s.title for s in got] == ["A", "B"]
    assert got[1].origin == "arxiv"


@pytest.mark.parametrize("store_cls", [SqliteCacheStore, FileJsonCacheStore])
def test_canonicalization_hit(tmp_path, store_cls):
    store = store_cls(_settings(tmp_path))
    store.set("wikipedia", "WHAT IS X?", [_source()])

    assert store.get("wikipedia", "what is x?") is not None
    assert store.get("wikipedia", "  what   is x?  ") is not None
    assert store.get("arxiv", "what is x?") is None


@pytest.mark.parametrize("store_cls", [SqliteCacheStore, FileJsonCacheStore])
def test_ttl_expiry(tmp_path, store_cls):
    store = store_cls(_settings(tmp_path, ttl=0))
    store.set("web", "expiring query", [_source()])
    time.sleep(0.05)
    assert store.get("web", "expiring query") is None


def test_clear(tmp_path):
    store = SqliteCacheStore(_settings(tmp_path))
    store.set("wikipedia", "q1", [_source()])
    store.set("arxiv", "q2", [_source()])
    store.clear()
    assert store.get("wikipedia", "q1") is None
    assert store.get("arxiv", "q2") is None


def test_file_cache_survives_process_restart(tmp_path):
    """FileJsonCacheStore's filename must not depend on Python's per-process
    hash salt, or a fresh CLI run could never find a file written by a
    previous run. Simulated with two subprocesses using different
    PYTHONHASHSEED, which is exactly what changes between real CLI runs.
    """
    import os
    import subprocess
    import sys

    cache_dir = tmp_path / "filecache"
    script = (
        "import sys; sys.path.insert(0, %r)\n"
        "from pathlib import Path\n"
        "from researcher.storage.cache_store import FileJsonCacheStore\n"
        "store = FileJsonCacheStore.__new__(FileJsonCacheStore)\n"
        "store._dir = Path(%r)\n"
        "print(store._path_for('web', 'What is X?').name)\n"
    ) % (str(Path(__file__).resolve().parents[1]), str(cache_dir))

    def run_with_seed(seed: str) -> str:
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run(
            [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True,
        )
        return out.stdout.strip()

    name_seed_0 = run_with_seed("0")
    name_seed_1 = run_with_seed("1")

    assert name_seed_0 == name_seed_1


def test_save_query_history(tmp_path):
    store = SqliteCacheStore(_settings(tmp_path))
    sources = [_source(title="A"), _source(title="B", origin="web")]
    store.save_query("What is X?", "X is ... [1][2]", sources)

    q_row = store._conn.execute("SELECT * FROM queries").fetchone()
    assert q_row["question"] == "What is X?"
    assert q_row["nquery"] == "what is x?"
    assert q_row["answer"] == "X is ... [1][2]"

    n = store._conn.execute("SELECT COUNT(*) AS n FROM query_sources").fetchone()["n"]
    assert n == 2