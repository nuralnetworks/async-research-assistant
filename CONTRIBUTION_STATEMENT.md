# Contribution Statement

**Team:** Topic Four
**Topic:** Topic 4 - Async Research Assistant
**Repository:** [https://github.com/nuralnetworks/async-research-assistant](https://github.com/nuralnetworks/async-research-assistant)
**Final tag:** `v1.0-final`
**Submission date:** 2026-09-18

---

## How to read this

Every member below wrote the files listed under their name, opened the listed pull requests from their own branch, and reviewed teammates' pull requests before merge. Work is split so each member owns a comparable share: core modules are divided one or two per person, every member wrote tests for their own code, and docs sections match code ownership. Every member can walk through any file in the repo during the defense.

Note on Emil's history: his commits are split across two emails (`...906@gmail.com`, `...906@email.com`) from two machines; both are his.

---

## Nural Shukurlu (`@nuralnetworks`)

**Owned (sole author):**
- `researcher/models.py` (+ `tests/test_models.py`)
- `researcher/services/ai_service.py` (+ `tests/test_ai_service.py`)
- `researcher/services/rate_limit.py` (+ `tests/test_rate_limit.py`)
- `researcher/config.py`, `researcher/logging_setup.py` (skeleton + fixes)
- `.env.example`, `pyproject.toml`, compliance touch-ups (cache versioning, query shaping, lint/CI fixes)
- PRs: #1, #13, #17, #18, #19

**Co-owned:**
- `researcher/concurrency/orchestrator.py` (shared-client fix: redirects + user agent)

**Reviewed:**
- Emil's storage/orchestrator PRs (#2 and follow-ups), Mahammadali's pipeline PRs, Bailar's CLI/Docker PRs — one approval each per the review circle before merge.


---

## Emil Mammadov (`@Emilsdeyta`)

**Owned (sole author):**
- `researcher/storage/cache_store.py` (SQLite + file fallback, `CacheStore` ABC)
- `researcher/concurrency/orchestrator.py` (parallel fetch, timeouts, degradation)
- `tests/test_cache_store.py`, `tests/test_orchestrator.py`
- PRs: #2, #4

**Co-owned:**
- `researcher/services/ai_service.py` (cache interface both sides honor)

**Reviewed:**
- Nural's resilience and touch-up PRs, Mahammadali's pipeline PRs per the review circle.


---

## Mahammadali Babayev (`@mahammadalibabayev11`)

**Owned (sole author):**
- `researcher/core/researcher.py` (the `ask` pipeline)
- `scripts/demo.py`, `scripts/bench.py` (5-question digest + benchmark harness)
- `tests/test_researcher.py`
- `artefacts/` outputs from live demo runs
- PRs: #3, #5

**Co-owned:**
- `researcher/concurrency/orchestrator.py` (pipeline/orchestrator boundary with Emil)

**Reviewed:**
- Nural's and Bailar's PRs per the review circle.


---

## Bailar Bayramov (`@bailar`)

**Owned (sole author):**
- `researcher/cli.py`, `researcher/__main__.py` (all three commands, validation, rendering)
- `Dockerfile`, `.dockerignore`
- `.github/workflows/ci.yml` (lint + typecheck + test + docker build)
- `tests/test_cli.py`
- `README.md` (runbook, env table, benchmark table)
- Report + slides assembly
- PRs: #7 (plus iterations superseded before final: #8, #9, #10, #14)

**Co-owned:**
- `researcher/core/researcher.py` (CLI/core error contract: clean `error:` exits)

**Reviewed:**
- Nural's, Emil's, and Mahammadali's PRs per the review circle.


---

## AI tool disclosure (also in §9 of the report)

We used AI coding assistance across the project as general productivity tooling, to avoid wasting time on routine implementation work. Drafts and boilerplate came faster with it; design decisions, debugging, and verification stayed with us. Every file below was read, run, and tested by its owner, and we can defend all of it in the oral defense. "The AI wrote it" is not an answer we will use.

---

## Signatures

By signing below, we affirm that:
- The contributions described above are accurate.
- Every line of code in the repository can be defended by at least one team member.
- AI assistant usage has been disclosed as described above.

| Member | Signature | Date |
|---|---|---|
| Nural Shukurlu | __________________________ | 2026-09-18 |
| Emil Mammadov | __________________________ | 2026-09-18 |
| Mahammadali Babayev | __________________________ | 2026-09-18 |
| Bailar Bayramov | __________________________ | 2026-09-18 |
