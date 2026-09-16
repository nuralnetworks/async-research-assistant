# Async Research Assistant

## Bailar: CLI, deployment and assembly

AI-ENG-110 / AI Academy / Topic 4

Prepared 17 September 2026. Team: Nural, Emil, Mahammadali and Bailar.
This report completes Bailar's sections and records integration evidence.
The other members' authored report sections and six slides have not been supplied.
This is a contribution report, not a declaration that the final team release is ready.

## Command-line interface

The entry point is `python -m researcher`. Argparse exposes `ask`, `demo`
and `bench`. Questions must contain 3 to 2000 characters after trimming.
The CLI delegates model validation to ResearchRequest. The `wiki` alias becomes
`wikipedia`; invalid source names and source limits exit with status 2.
The accepted source limit is 1 to 10. The core applies its configured cap.

`ask` renders the question, answer, numbered references with URLs and optional
warnings. JSON output uses AnswerWithCitations.to_dict() plus timings_ms, so
citations contain index, title, url and origin. Logs go to stderr while JSON
stays on stdout. Expected operational errors exit 1 with a short message.

`--offline` supplies canned sources and a fake synthesizer, requiring no API
keys. Its answer labels the demonstration explicitly. Synthetic arXiv/web
references use example.test rather than misrepresenting a real publication.
`--no-cache` uses a null store without constructing SQLite. The service adapter
forwards use_cache=False and absorbs writes through the null store.

CLI unit tests replace Researcher with a fake. They verify argument failures,
alias forwarding, cache bypass, cache closure after success and failure, JSON,
citations, warning rendering and demo/benchmark dispatch. Separate tests exercise
the local OfflineService with HTTP calls forbidden.

## Docker and continuous integration

The two stages use python:3.12.6-slim. The builder installs the existing pinned
requirements into /opt/venv. The runtime copies that environment and runs as
appuser. /app is owned by appuser so SQLite, artefacts and benchmark output can
be written. The default command displays ask help.

The Docker context excludes environment files, databases, logs, caches and
report/slide build outputs. Offline runs need neither .env nor credentials.
For live runs, pass an existing private .env file at runtime.

CI runs lint, type checking, pytest with a 60% coverage threshold, and a Docker
build on pull requests. Tools come from requirements.txt without unpinned
upgrades. The Docker job checks help, a non-root UID and all three offline
commands with --network none. Repository branch protection must require these
jobs for failures to block merging; editing YAML alone cannot enforce that.

Docker is unavailable on this development machine. Image build/run and the
required second-machine validation remain unverified until CI or a teammate
with Docker executes them. No passing Docker result is claimed here.

## Measured verification

Python 3.12.10 on Windows 11 build 26200, AMD64, 12 logical CPUs.
All 86 offline tests passed. researcher coverage: 93.04%. CLI coverage: 94%.
The CLI and AI smoke subset passed 43 tests. Scoped Ruff checks passed.
Scoped mypy with --follow-imports=silent passed for researcher/cli.py.

The normal suite encountered Windows access errors creating restricted pytest
temporary folders. The verification launcher changed only os.mkdir's mode to
0o777 inside the test process and used a workspace temporary directory. Test
assertions and repository files were unchanged. This environment workaround
must not be mistaken for verification on another operating system.

Mahammadali's benchmark ran unchanged with output and SQLite paths redirected
to scratch files. Five questions used three sources and 300 ms simulated I/O
per source, with a cleared cache and semaphore 3. Sequential: 4.661 seconds.
Concurrent: 3.202 seconds. Speedup: 1.46x. See benchmark.md for captured details.
The run measures fetching, not live providers or LLM synthesis. Client setup
and scheduling remain in the measured concurrent path. One run is not an SLA.
The unchanged demo also completed all five offline questions in scratch output.

## Integration handoff

Global mypy reports three pre-existing errors: researcher/config.py:42 (_Env
redefinition), researcher/logging_setup.py:16 (optional string), and
ai/providers/openai.py:143 (optional dictionary key). Global Ruff reports 16
issues in scripts/bench.py, scripts/demo.py, demo_ai.py and tests/test_ai_smoke.py.
These files belong to other owners or are frozen and remain unchanged.

Full requirements installation on this Windows machine stopped while building
pyreqwest-impersonate, required by duckduckgo-search==6.1.0, because the build
needs Rust. Offline checks used the pinned core/testing packages. No dependency
versions changed. Live providers and full installation remain unverified here.

researcher.db is already tracked on main, contrary to the final-release rule.
The team must coordinate its removal. Other owners must resolve their lint/type
errors and provide their report sections and slides before final assembly.
The reviewer assigned to Bailar is Mahammadali. The author merges after approval.
Keep each PR below 300 changed lines; submit these commits in separate reviews
where needed. Squashing changes the commit-share arithmetic.

## AI disclosure and ownership

Codex assisted Bailar with edits to researcher/cli.py, tests/test_cli.py,
Dockerfile, .dockerignore, .github/workflows/ci.yml and the Docker/timings
sections of README.md, and with these report/slides materials. It ran offline
checks and drafted the explanation. Bailar must review and understand the
changes before submission. No work is attributed to another member and no
other member's implementation files were edited.

## Evidence sources

The supplied team ownership rules; docs/architecture.md; researcher/cli.py;
tests/test_cli.py; Dockerfile; .github/workflows/ci.yml; scripts/bench.py;
scripts/demo.py; and the local test, Ruff and mypy outputs from this session.
