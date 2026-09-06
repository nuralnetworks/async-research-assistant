# Architecture

We ask three sources at once (Wikipedia, arXiv, web), then pass what came back to the LLM in `ai/` for a short cited answer. Our code sits around `ai/`: config, cache, retries, parallel fetch, and the CLI.

```
CLI -> core/Researcher -> concurrency/Orchestrator -+-> services/ResilientAIService -> ai/
                                                      +-> storage/CacheStore (SQLite)
```

Only `services/ai_service.py` calls `ai/`. Only the service and core read and write storage. Nothing else touches those boundaries. We pass pydantic models between modules, not plain dicts.

## Files

`researcher/config.py` reads env and builds a frozen Settings object. Everyone imports from here.

`researcher/logging_setup.py` sets up stdlib logging from LOG_LEVEL.

`researcher/models.py` has ResearchRequest, SourceFailure and ResearchResult.

`researcher/services/ai_service.py` wraps every `ai.*` call with retries, timeouts and logging.

`researcher/services/rate_limit.py` is a small token bucket used before external calls.

`researcher/storage/cache_store.py` is the (source, query) cache. SQLite is the main one, files under CACHE_DIR are the fallback.

`researcher/concurrency/orchestrator.py` runs the three fetches together.

`researcher/core/researcher.py` ties it together: validate, fetch, synthesize, save history.

`researcher/cli.py` and `researcher/__main__.py` handle `python -m researcher`.

`scripts/demo.py` runs the 5 sample questions. `scripts/bench.py` times sequential against concurrent.

## Interfaces

Config:

```python
@dataclass(frozen=True)
class Settings:
    llm_provider: str
    llm_model: str
    web_search_provider: str
    log_level: str
    cache_dir: Path
    cache_ttl_seconds: int
    per_source_timeout_seconds: float
    max_sources_per_query: int
    max_parallel: int
    retry_attempts: int
    retry_min_wait: float
    retry_max_wait: float
    database_url: str

def get_settings() -> Settings: ...
def canonicalize_query(q: str) -> str: ...
```

`canonicalize_query` lowercases, strips and collapses whitespace. We use it for all cache keys so "WHAT IS PHOTOSYNTHESIS?" hits the same entry.

Models:

```python
class ResearchRequest(BaseModel):
    question: str
    sources: tuple[str, ...] = ("wikipedia", "arxiv", "web")
    use_cache: bool = True
    max_sources_per_query: int = 3

class SourceFailure(BaseModel):
    source: str
    error: str

class ResearchResult(BaseModel):
    question: str
    answer: str
    citations: list[Citation]
    sources: list[Source]
    failures: list[SourceFailure]
    timings_ms: dict[str, float]
    cache_hit: bool
    warnings: list[str]
```

Questions are 3 to 2000 chars. Sources can only be wikipedia, arxiv or web. `wiki` on the command line means wikipedia.

Cache:

```python
class CacheStore(ABC):
    def get(self, source: str, query: str) -> list[Source] | None: ...
    def set(self, source: str, query: str, value: list[Source]) -> None: ...
    def clear(self) -> None: ...

class SqliteCacheStore(CacheStore): ...
class FileJsonCacheStore(CacheStore): ...
```

Tables:

```sql
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
```

Service layer:

```python
class ResilientAIService:
    def __init__(self, settings: Settings, cache: CacheStore, limiter: TokenBucket) -> None: ...
    async def fetch_one(self, source: str, query: str, client: httpx.AsyncClient | None = None) -> list[Source]: ...
    def synthesize(self, question: str, sources: list[Source]) -> AnswerWithCitations: ...
```

Retries 3 times with exponential backoff from 1 to 8 seconds plus jitter, only on ProviderError and httpx errors. Each call has a timeout. We log source, duration and cache hit at info level, full payloads at debug. Keys never go into logs.

Rate limit:

```python
class TokenBucket:
    def __init__(self, rate_per_sec: float, capacity: int) -> None: ...
    async def acquire(self) -> None: ...
```

Orchestrator:

```python
@dataclass(frozen=True)
class FetchOutcome:
    sources: list[Source]
    failures: list[SourceFailure]
    timings_ms: dict[str, float]

async def fetch_all(question: str, sources: tuple[str, ...], settings: Settings, svc: ResilientAIService) -> FetchOutcome: ...
```

One shared httpx client, semaphore to cap concurrency, a timeout per source, gather with return_exceptions set so one dead source does not kill the other two.

Core:

```python
class Researcher:
    def __init__(self, settings: Settings, svc: ResilientAIService) -> None: ...
    async def ask(self, req: ResearchRequest) -> ResearchResult: ...
```

Validate, fetch, raise ResearchError if nothing came back at all, otherwise synthesize and save. If only some sources failed we still answer and put a note in warnings.

CLI:

```
python -m researcher ask "question" [--sources wiki,arxiv,web] [--no-cache] [--json] [--offline] [--max-sources N]
python -m researcher demo [--limit 5] [--offline]
python -m researcher bench [--offline]
```

Output looks like this:

```
Q: <question>
A: <answer with [N] markers>

References:
  [1] (wikipedia) Title
      https://...
```

Bad input prints a short error and exits 2, no traceback.

## Rules we follow

Logging goes through the logging module. Print is only for what the user asked to see.

We catch specific errors (ProviderError, httpx errors, ValueError), log them and either retry or record a SourceFailure. No bare except, no silent pass.

`.env`, `*.db` and `*.log` stay local. We check git status before pushing.

`ai/` stays as shipped. We check with diff before opening a PR.

All public functions have type hints. We run mypy and keep the result for the report.

Tests run offline with respx and fake providers. Nothing in pytest needs network.

## Bench and demo

`scripts/bench.py --offline` runs the same 5 questions one source at a time and then all together, cache cleared, and prints a small table. We paste that into the README.

`scripts/demo.py --offline --limit 5` runs everything in data/research_questions.json and writes artefacts/answers.json plus a markdown digest with citations.
