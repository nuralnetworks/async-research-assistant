# Docker Run Proof

Async Research Assistant / Bailar / verified 18 September 2026 (Asia/Baku)

## Reproducible evidence

[Successful Docker job](https://github.com/nuralnetworks/async-research-assistant/actions/runs/35284135541/job/105412575476)

GitHub Actions job 105412575476, run 35284135541, completed successfully at
2026-09-17 22:52:46 UTC (18 September, 02:52:46 in Baku). The PR head was
f090268b42a0af6f78cd608fb4b6f5a164ec11cd. Actions checked out the PR merge ref.
The workflow is .github/workflows/ci.yml. The runner is ubuntu-latest and the
container uses Python 3.12.6. This proves a remote Linux run, not local Docker.

## Commands that passed

`docker build -t finalproj .`

`docker run --rm --network none finalproj`

`test "$(docker run --rm --network none finalproj id -u)" != "0"`

`docker run --rm --network none finalproj python -m researcher ask "What is photosynthesis?" --offline --json`

`docker run --rm --network none finalproj python -m researcher demo --offline --limit 1`

`docker run --rm --network none finalproj python -m researcher bench --offline`

The build, default-help/non-root step and offline-command step all returned
success. The smoke commands used fresh containers and disabled network access.
No .env file or API keys were supplied to these containers.

## Observed output

Ask returned JSON with the question, an explicitly labelled offline answer,
three numbered citations and timings_ms. The demo saved /app/artefacts/answers.json
and /app/artefacts/digest-2026-09-17.md. The benchmark processed five questions,
15 sources in each mode and saved /app/bench_result.md.

That CI run measured sequential 4.508 seconds and parallel 1.627 seconds,
reported as 2.77x. These are simulated I/O timings from this Linux container,
not live-provider performance or a replacement for the Windows benchmark record.

## Fix and scope

The earlier image build failed with "linker cc not found" while compiling
pyreqwest-impersonate. Nural's main commit e03e8cf pinned version 0.5.3, which
provides the wheel. Bailar integrated that commit and retained the writable
appuser working directory and offline container smoke checks.

The second successful verification at head 2367301 is available in
[run 35284351793](https://github.com/nuralnetworks/async-research-assistant/actions/runs/35284351793).
This evidence does not claim live Gemini access, review approval or final release.
