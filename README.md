# Async research assistant

Ask a question, we pull Wikipedia, arXiv and web search at the same time, then write one short answer with [N] citations.

Team: Nural, Emil, Mahammadali, Bailar. AI-ENG-110, AI Academy, Topic 4.

## Quick start

```bash
git clone https://github.com/nuralnetworks/async-research-assistant
cd async-research-assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# open .env and add your keys

python demo_ai.py --offline
pytest tests/test_ai_smoke.py -v

pytest
python -m researcher ask "What is photosynthesis?" --offline
```

On Windows use `.venv\Scripts\activate` instead of `source`.

## Docker

```bash
docker build -t finalproj .
docker run --rm --network none finalproj python -m researcher ask "What is photosynthesis?" --offline
docker run --rm --network none finalproj python -m researcher demo --offline --limit 5
docker run --rm --network none finalproj python -m researcher bench --offline
```

Offline commands need no `.env` or API keys. For a live query, supply your own
`.env` with `--env-file .env` and omit both `--offline` and `--network none`.
The image uses Python 3.12.6, copies a builder virtual environment, and runs
as `appuser`. The working directory is writable so demo and benchmark outputs
can be created. Copy outputs before removing a container if you need to keep them.
The Docker CI job builds a fresh image and runs these commands with networking
disabled. Local Docker verification is still pending because the development
machine used for this update has no Docker executable.

## Env vars

| Variable | Needed? | Default | What it does |
|---|---|---|---|
| `LLM_PROVIDER` | yes | `gemini` | `anthropic`, `openai` or `gemini` |
| `LLM_MODEL` | yes | `gemini-2.0-flash` | model name |
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | one of them for live runs | - | key for the LLM you picked. Not needed with `--offline` |
| `WEB_SEARCH_PROVIDER` | yes | `duckduckgo` | `tavily`, `serper` or `duckduckgo` |
| `TAVILY_API_KEY` / `SERPER_API_KEY` | only if you use that search | - | DuckDuckGo needs no key |
| `LOG_LEVEL` | no | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `CACHE_DIR` | no | `./.cache` | where the file cache lives |
| `CACHE_TTL_SECONDS` | no | `86400` | how long a cached (source, query) lasts |
| `PER_SOURCE_TIMEOUT_SECONDS` | no | `10` | timeout per source |
| `MAX_SOURCES_PER_QUERY` | no | `3` | how many hits we ask each source for |
| `MAX_PARALLEL` | no | `5` | max concurrent fetches |
| `RETRY_ATTEMPTS` / `RETRY_MIN_WAIT` / `RETRY_MAX_WAIT` | no | `3` / `1` / `8` | retry backoff |
| `DATABASE_URL` | no | `sqlite:///./researcher.db` | history and cache db |

Same list is in `.env.example`. Keep your real `.env` local, it is gitignored.

## Running it

```bash
# one question, no keys needed
python -m researcher ask "What is photosynthesis and what are its main stages?" --offline

# only two sources, skip cache
python -m researcher ask "How does CRISPR-Cas9 work?" --sources wiki,arxiv --no-cache --offline

# json output
python -m researcher ask "What is fusion energy?" --offline --json

# all 5 sample questions in data/research_questions.json
python -m researcher demo --limit 5 --offline

# timing test
python -m researcher bench
```

`python -m researcher demo --limit 5 --offline` writes one answer per question plus `artefacts/answers.json`.

## Timings

Numbers come from Mahammadali's `run_benchmark()` in `scripts/bench.py`, rerun
on 2026-09-17 with a separate, cleared SQLite cache and no network calls.

| Workload | N | Sequential | Concurrent (sem=3) | Speedup |
|---|---|---|---|---|
| 5 questions x 3 sources, 300ms fake IO | 15 fetches | 4.661 s | 3.202 s | 1.46x |

```bash
python scripts/bench.py --offline
python -m researcher bench --offline
```

Machine: Windows 11 build 26200, AMD64 Family 25 Model 68, 12 logical CPUs,
CPython 3.12.10. The captured output is in `report/benchmark.md`.
This measures simulated fetching only, not LLM synthesis or real provider latency.
Client creation and scheduling overhead remain in the concurrent path, so this
single run is below the ideal 3x overlap and should not be treated as a live SLA.

## Tests

```bash
pytest --cov=researcher --cov-report=term-missing
pytest tests/test_ai_smoke.py -v
mypy researcher/
```

We aim for 60%+ coverage on `researcher/`. The ai smoke tests have to stay green. Everything runs offline, ai and http are mocked.

## Layout

```
.
├── ai/
├── researcher/
│   ├── config.py
│   ├── logging_setup.py
│   ├── models.py
│   ├── services/
│   ├── storage/
│   ├── concurrency/
│   ├── core/
│   ├── cli.py
│   └── __main__.py
├── scripts/
├── tests/
├── data/research_questions.json
├── artefacts/
├── docs/architecture.md
├── report/
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## How it fits together

```
CLI -> core/Researcher -> concurrency/Orchestrator -+-> services/ResilientAIService -> ai/
                                                      +-> storage/CacheStore (SQLite)
```

Only the service layer talks to `ai/`. Only the service and core touch storage. `ai/` itself we leave as is.

## Limits

- SQLite is single writer, so it will not scale past one process. Postgres would be next.
- If the LLM provider is down we have no second provider to fall back to.
- Rate limiting is per process, not shared.

Built for AI-ENG-110 at AI Academy.
