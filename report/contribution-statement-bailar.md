# Contribution Statement: Bailar

Async Research Assistant / AI-ENG-110 / 18 September 2026

## Assigned responsibility

Bailar owns the CLI, Docker packaging, CI, CLI tests, Docker/timing documentation
and document assembly. This statement describes Git-recorded work with disclosed
AI assistance, not authorship of the entire project.

## Implemented contribution

The initial CLI/Docker/CI contribution is commit e103c55. Subsequent work added
offline benchmark argument support and validation tests (939f414), real cache
bypass and concise failure handling (093170e), isolated CLI tests and corrected
offline references/JSON checks (5fe6bef), writable non-root container outputs
and offline CI smoke tests (3572a8b), and measured README updates (081910a).

Bailar assembled his report and four presentation slides in cf1e683 and updated
them with successful Docker/CI evidence in 4379501. The first review stage now
installs the pinned lint dependencies (8e5b1cd). The three PRs were synchronized
with main while preserving the team's .env loading and service changes.

## Verification and evidence

The integrated branch passed 92 offline tests with 93.33% researcher coverage
and 94% CLI coverage. Project lint and mypy for all 15 researcher files passed.
GitHub Actions verified Docker build, help, a non-root UID, offline ask JSON,
demo output and benchmark output with networking disabled. Docker run proof
identifies the verified commit and job so the result can be independently checked.

Windows tests needed a temporary-directory permission workaround; Linux CI did
not. No live provider test or local Windows Docker run is claimed.

## Attribution and AI assistance

Nural's e03e8cf supplied the dependency pin and shared compliance/live fixes.
Emil owns cache/storage and orchestration. Mahammadali owns the core, demo and
benchmark. Those implementations were integrated, not independently authored
by Bailar. Benchmark figures came from Mahammadali's script.

Codex assisted Bailar's CLI fixes, unit tests, Docker/CI edits, Git operations,
documentation, slide generation and validation. Bailar is responsible for
reviewing the changes, understanding them and following the course AI policy.
This document is not signed and does not assert an instructor-approved score.

## Review and submission status

PRs #8, #9 and #10 contain the implementation and report/slides. Mahammadali is
the assigned reviewer. Merge commits are integration operations, not extra
feature contributions. Final contribution percentages must be calculated on
the accepted main history using the course's counting rule.

Team assembly awaits the other members' statements, report sections and slides.
The final tag and Moodle upload are deferred until team approval.
