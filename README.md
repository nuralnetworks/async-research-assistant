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
docker run --env-file .env finalproj python -m researcher ask "What is photosynthesis?" --offline
```

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
python -m researcher bench --offline
```

`python -m researcher demo --limit 5 --offline` writes one answer per question plus `artefacts/answers.json`.

## Timings

Numbers come from `scripts/bench.py --offline` on the same machine with a cleared cache.

| Workload | N | Sequential | Concurrent (sem=5) | Speedup |
|---|---|---|---|---|
| 5 questions x 3 sources, 300ms fake IO | 15 fetches | tbd | tbd | tbd |

```bash
python scripts/bench.py --offline
```

After we parallelize, what is left is mostly network round trip plus the one LLM call for synthesis. Full table and machine info are in the report.

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
