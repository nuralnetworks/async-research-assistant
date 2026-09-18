# Async Research Assistant

## Bailar: CLI, deployment and assembly

AI-ENG-110 / AI Academy / Topic 4

Updated 18 September 2026. Team: Nural, Emil, Mahammadali and Bailar.
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

GitHub's Linux runner verified the image build, non-root UID and all three
offline commands in fresh containers with networking disabled. Evidence:
Actions run 35284135541, job 105412575476, head f090268. All steps passed.
This is remote CI proof, not a claim of a local Windows Docker run.

## Measured verification

Python 3.12.10 on Windows 11 build 26200, AMD64, 12 logical CPUs.
All 92 offline tests passed. researcher coverage: 93.33%. CLI coverage: 94%.
The CLI and AI smoke subset passed 43 tests. Project Ruff checks passed.
Full mypy researcher/ passed across 15 source files. Remote CI also passed
lint, typecheck, test and Docker for the verified head f090268.

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

Nural's main update e03e8cf fixed the dependency selection, cleaned tracked
databases/bytecode and configured the lint/type checks. Bailar integrated it
without claiming those changes as his own. pyreqwest-impersonate==0.5.3 provides
the binary wheel, avoiding the missing C linker that broke the old build.
Full pinned requirements now install on Windows and in the CI container.

Other members will prepare their authored report sections, contribution
statements and slides after technical verification. The assembled team report
therefore remains pending. Live provider calls were not repeated in this run.
The team's model/README update belongs to Emil and is not claimed by Bailar.
The reviewer assigned to Bailar is Mahammadali. The author merges after approval.
Keep each PR below 300 changed lines; submit these commits in separate reviews
where needed. Squashing changes the commit-share arithmetic.
The v1.0-final tag and Moodle upload remain deferred by the team's instruction.

## AI disclosure and ownership

Codex assisted Bailar with edits to researcher/cli.py, tests/test_cli.py,
Dockerfile, .dockerignore, .github/workflows/ci.yml and the Docker/timings
sections of README.md, and with these report/slides materials. It ran offline
checks and drafted the explanation. Bailar must review and understand the
changes before submission. No work is attributed to another member and no
other member's implementation changes were independently authored here;
updates from main retain their existing authorship.

## Evidence sources

The supplied team ownership rules; docs/architecture.md; researcher/cli.py;
tests/test_cli.py; Dockerfile; .github/workflows/ci.yml; scripts/bench.py;
scripts/demo.py; local test, Ruff and mypy results; GitHub Actions run
35284135541; and the team integration commit e03e8cf.
