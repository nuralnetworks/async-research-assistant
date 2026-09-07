"""(source, query) cache with TTL, plus query history."""

from __future__ import annotations

import json
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ai.schemas import Source
from researcher.config import Settings, canonicalize_query

logger = logging.getLogger(__name__)


class CacheStore(ABC):
    @abstractmethod
    def get(self, source: str, query: str) -> list[Source] | None: ...

    @abstractmethod
    def set(self, source: str, query: str, value: list[Source]) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


def _resolve_sqlite_path(database_url: str) -> str:
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return database_url[len(prefix):]
    return database_url


class SqliteCacheStore(CacheStore):
    """Main cache backend. Also logs query history for the CLI/report."""

    def __init__(self, settings: Settings) -> None:
        db_path = _resolve_sqlite_path(settings.database_url)
        parent = Path(db_path).parent
        if str(parent) not in ("", "."):
            parent.mkdir(parents=True, exist_ok=True)
        self._ttl = settings.cache_ttl_seconds
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cache_entries(
              source TEXT NOT NULL, nquery TEXT NOT NULL,
              payload_json TEXT NOT NULL, expires_at TEXT NOT NULL,
              PRIMARY KEY(source, nquery));
            CREATE TABLE IF NOT EXISTS queries(
              id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT NOT NULL,
              nquery TEXT NOT NULL, answer TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS query_sources(
              id INTEGER PRIMARY KEY AUTOINCREMENT, query_id INTEGER NOT NULL REFERENCES queries(id),
              origin TEXT NOT NULL, title TEXT NOT NULL, url TEXT NOT NULL, snippet TEXT NOT NULL);
            """
        )
        self._conn.commit()

    def get(self, source: str, query: str) -> list[Source] | None:
        nquery = canonicalize_query(query)
        row = self._conn.execute(
            "SELECT payload_json, expires_at FROM cache_entries WHERE source = ? AND nquery = ?",
            (source, nquery),
        ).fetchone()
        if row is None:
            return None

        if datetime.now(timezone.utc) >= datetime.fromisoformat(row["expires_at"]):
            logger.debug("cache expired source=%s nquery=%s", source, nquery)
            self._conn.execute(
                "DELETE FROM cache_entries WHERE source = ? AND nquery = ?",
                (source, nquery),
            )
            self._conn.commit()
            return None

        raw = json.loads(row["payload_json"])
        return [Source.model_validate(item) for item in raw]

    def set(self, source: str, query: str, value: list[Source]) -> None:
        nquery = canonicalize_query(query)
        payload_json = json.dumps([json.loads(s.model_dump_json()) for s in value])
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self._ttl)).isoformat()
        self._conn.execute(
            "INSERT INTO cache_entries (source, nquery, payload_json, expires_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(source, nquery) DO UPDATE SET "
            "payload_json = excluded.payload_json, expires_at = excluded.expires_at",
            (source, nquery, payload_json, expires_at),
        )
        self._conn.commit()

    def clear(self) -> None:
        self._conn.execute("DELETE FROM cache_entries;")
        self._conn.commit()

    def save_query(self, question: str, answer: str, sources: list[Source]) -> None:
        nquery = canonicalize_query(question)
        created_at = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO queries (question, nquery, answer, created_at) VALUES (?, ?, ?, ?)",
            (question, nquery, answer, created_at),
        )
        query_id = cur.lastrowid
        self._conn.executemany(
            "INSERT INTO query_sources (query_id, origin, title, url, snippet) "
            "VALUES (?, ?, ?, ?, ?)",
            [(query_id, s.origin, s.title, s.url, s.snippet) for s in sources],
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()


class FileJsonCacheStore(CacheStore):
    """Fallback cache backend, one JSON file per (source, query)."""

    def __init__(self, settings: Settings) -> None:
        self._ttl = settings.cache_ttl_seconds
        self._dir = Path(settings.cache_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path_for(self, source: str, query: str) -> Path:
        nquery = canonicalize_query(query)
        digest = abs(hash((source, nquery)))
        return self._dir / f"{source}__{digest}.json"

    def get(self, source: str, query: str) -> list[Source] | None:
        p = self._path_for(source, query)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        if datetime.now(timezone.utc) >= datetime.fromisoformat(data["expires_at"]):
            p.unlink(missing_ok=True)
            return None
        return [Source.model_validate(item) for item in data["payload"]]

    def set(self, source: str, query: str, value: list[Source]) -> None:
        p = self._path_for(source, query)
        expires_at = (datetime.now(timezone.utc) + timedelta(seconds=self._ttl)).isoformat()
        payload = {
            "expires_at": expires_at,
            "payload": [json.loads(s.model_dump_json()) for s in value],
        }
        p.write_text(json.dumps(payload))

    def clear(self) -> None:
        for f in self._dir.glob("*.json"):
            f.unlink(missing_ok=True)