# Dataset Foundry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-first synthetic training-data workbench that imports a small seed dataset, generates thousands of schema-valid examples, filters low-quality and near-duplicate candidates, supports human review, and produces immutable fine-tuning exports.

**Architecture:** A FastAPI API is the sole data boundary for a React workbench, CLI, and a SQLite-backed worker. Provider adapters use native Pydantic structured outputs for OpenAI and Anthropic, while a deterministic offline provider makes every core flow testable without keys; all candidates pass through structural, quality, and vector-similarity gates before immutable Parquet and JSONL export.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2, SQLite, PyArrow, OpenAI/Anthropic Python SDKs, React 19, TypeScript, Vite, TanStack Query, Cypress component tests, Playwright E2E, uv, Ruff, mypy, pytest, Docker Compose.

---

## File structure

```text
dataset-foundry/
├── src/dataset_foundry/
│   ├── api/                 # FastAPI app, routes, middleware, response errors
│   ├── domain/              # Pydantic schemas, enums, state transitions
│   ├── ingestion/           # JSON/JSONL/CSV/Parquet normalization
│   ├── generation/          # recipes, prompt construction, orchestration
│   ├── providers/           # deterministic, OpenAI, Anthropic adapters
│   ├── quality/             # scoring, embeddings, cosine deduplication
│   ├── persistence/         # SQLAlchemy models, repositories, DB setup
│   ├── jobs/                # queue, leases, worker, cancellation, recovery
│   ├── exports/             # Parquet, canonical, OpenAI chat, Alpaca, manifests
│   ├── cli.py               # serve, worker, demo, generate, export, doctor
│   ├── config.py            # typed settings and safe defaults
│   └── container.py         # dependency assembly
├── frontend/src/
│   ├── api/                 # typed fetch client and query hooks
│   ├── components/          # reusable workbench primitives
│   ├── features/            # overview, projects, runs, review, exports, settings
│   ├── styles/              # tokens, shell, components, responsive states
│   ├── App.tsx              # route-free workbench shell
│   └── main.tsx             # React entry point
├── tests/                   # unit, integration, contract, scale, and live-provider tests
├── frontend/cypress/        # React component tests only
├── frontend/tests/e2e/      # Playwright E2E only
├── docs/                    # adopter docs, completion record, proof, handoff
├── examples/                # versioned seed datasets and recipes
├── scripts/                 # demo bootstrap and scale benchmark
├── pyproject.toml
├── uv.lock
├── Makefile
├── Dockerfile
└── compose.yaml
```

### Task 1: Repository and contracts

**Files:**
- Create: `pyproject.toml`, `.python-version`, `.gitignore`, `.env.example`, `Makefile`
- Create: `src/dataset_foundry/domain/models.py`, `src/dataset_foundry/domain/states.py`, `src/dataset_foundry/config.py`
- Test: `tests/unit/test_domain_models.py`, `tests/unit/test_state_transitions.py`

- [ ] **Step 1: Write failing domain tests**

```python
def test_training_example_requires_user_then_assistant() -> None:
    with pytest.raises(ValidationError):
        TrainingExample(messages=[ChatMessage(role="assistant", content="orphan")])


def test_recipe_rejects_unbounded_candidate_budget() -> None:
    with pytest.raises(ValidationError):
        GenerationRecipe(name="unsafe", target_count=100, candidate_multiplier=21)
```

- [ ] **Step 2: Run the focused tests and verify collection or symbol failures**

Run: `uv run pytest tests/unit/test_domain_models.py tests/unit/test_state_transitions.py -q`

Expected: tests fail because the package and contracts do not exist.

- [ ] **Step 3: Implement the canonical contracts**

Define `ChatMessage`, `TrainingExample`, `GenerationRecipe`, `GeneratedCandidate`, `QualityReport`, `RunSummary`, `ReviewDecision`, and `ExportManifest` with `ConfigDict(extra="forbid")`. Enforce the canonical system/user/assistant order, target range `1..10_000`, batch range `1..50`, candidate multiplier `1..20`, quality range `0..1`, and legal run transitions:

```python
ALLOWED_RUN_TRANSITIONS = {
    RunStatus.queued: {RunStatus.running, RunStatus.cancelled},
    RunStatus.running: {RunStatus.completed, RunStatus.failed, RunStatus.cancelled},
    RunStatus.completed: set(),
    RunStatus.failed: set(),
    RunStatus.cancelled: set(),
}
```

- [ ] **Step 4: Add typed settings and dependency groups**

Pin each pre-1.0 dependency to a tested minor line, keep provider model IDs configurable, default to `offline`, bind to `127.0.0.1`, and never expose provider credentials to frontend settings responses.

- [ ] **Step 5: Run unit tests, Ruff, and mypy**

Run: `uv run pytest tests/unit/test_domain_models.py tests/unit/test_state_transitions.py -q && uv run ruff check src tests && uv run mypy src`

Expected: all checks pass.

- [ ] **Step 6: Commit the contract slice**

Run: `git add pyproject.toml uv.lock .python-version .gitignore .env.example Makefile src tests && git commit -m "feat: define Dataset Foundry contracts"`

### Task 2: Persistence, ingestion, and fingerprints

**Files:**
- Create: `src/dataset_foundry/persistence/database.py`, `models.py`, `repositories.py`
- Create: `src/dataset_foundry/ingestion/loaders.py`, `mapping.py`, `fingerprint.py`
- Test: `tests/unit/test_ingestion.py`, `tests/integration/test_repositories.py`
- Create: `examples/customer-support-seeds.jsonl`

- [ ] **Step 1: Write equivalent-format ingestion tests**

Build JSONL, JSON, CSV, and Parquet fixtures containing the same two instruction/input/output rows and assert every loader produces the same canonical fingerprint and ordered messages.

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `uv run pytest tests/unit/test_ingestion.py tests/integration/test_repositories.py -q`

Expected: imports fail until loaders and repositories exist.

- [ ] **Step 3: Implement bounded ingestion**

Accept `.json`, `.jsonl`, `.csv`, and `.parquet`; support `messages`, `instruction/input/output`, and `prompt/completion` mappings; reject unsupported extensions, files over the configured byte limit, more than 50,000 rows, blank required text, and malformed role sequences. Compute a stable SHA-256 fingerprint from canonical JSON with sorted metadata keys.

- [ ] **Step 4: Implement SQLite persistence**

Create datasets, seeds, recipes, runs, jobs, candidates, quality reports, reviews, exports, and audit events. Enable foreign keys, WAL, and a busy timeout; enforce candidate idempotency with `(run_id, candidate_fingerprint)` and job leasing with `lease_owner`, `lease_expires_at`, and `heartbeat_at`.

- [ ] **Step 5: Prove round-trips and idempotency**

Run: `uv run pytest tests/unit/test_ingestion.py tests/integration/test_repositories.py -q`

Expected: equivalent formats share one fingerprint, duplicate candidates do not create duplicate rows, and foreign-key violations fail.

- [ ] **Step 6: Commit the data slice**

Run: `git add src/dataset_foundry/persistence src/dataset_foundry/ingestion tests examples && git commit -m "feat: add seed ingestion and persistence"`

### Task 3: Structured providers and generation planning

**Files:**
- Create: `src/dataset_foundry/providers/base.py`, `offline.py`, `openai.py`, `anthropic.py`, `registry.py`
- Create: `src/dataset_foundry/generation/prompts.py`, `planner.py`
- Test: `tests/unit/test_offline_provider.py`, `tests/contract/test_provider_contracts.py`

- [ ] **Step 1: Write provider contract tests**

Assert the offline provider returns the requested batch size deterministically for a fixed recipe seed. Mock OpenAI `responses.parse` and Anthropic `messages.parse` to cover parsed success, refusal, incomplete/max-token output, timeout, rate limit, and invalid business constraints.

- [ ] **Step 2: Run contract tests and verify failure**

Run: `uv run pytest tests/unit/test_offline_provider.py tests/contract/test_provider_contracts.py -q`

Expected: provider imports fail.

- [ ] **Step 3: Implement one provider protocol and deterministic mode**

```python
class GenerationProvider(Protocol):
    async def generate_batch(
        self, request: GenerationBatchRequest
    ) -> CandidateBatch: ...
```

Generate offline variations from stable template families, seed strata, tone, difficulty, locale, and context axes. Preserve source-seed lineage and a provider trace labeled `offline-deterministic`; do not represent lexical template generation as a live LLM call.

- [ ] **Step 4: Implement native structured outputs**

Use OpenAI `AsyncOpenAI().responses.parse(..., text_format=CandidateBatch)` and Anthropic `AsyncAnthropic().messages.parse(..., output_format=CandidateBatch)`. Validate parsed output again with Pydantic, classify refusals and truncations as terminal attempt evidence, and retry only bounded transient network/rate/server failures.

- [ ] **Step 5: Add budget and privacy preflight**

Calculate maximum candidates, calls, and estimated tokens before enqueueing. Require explicit `allow_external_data_transfer=true` for live providers; never silently fall back from OpenAI or Anthropic to offline mode.

- [ ] **Step 6: Run provider tests and commit**

Run: `uv run pytest tests/unit/test_offline_provider.py tests/contract/test_provider_contracts.py -q`

Expected: all offline and mocked-provider cases pass without API credentials.

Run: `git add src/dataset_foundry/providers src/dataset_foundry/generation tests && git commit -m "feat: add structured generation providers"`

### Task 4: Quality, vector similarity, and review truth

**Files:**
- Create: `src/dataset_foundry/quality/embeddings.py`, `similarity.py`, `scorers.py`, `pipeline.py`
- Test: `tests/unit/test_quality_pipeline.py`, `tests/unit/test_similarity.py`

- [ ] **Step 1: Write exact and near-duplicate boundary tests**

Assert exact normalized duplicates always reject, configured cosine fixtures at `0.919` pass when threshold is `0.92`, fixtures at `0.921` reject, and every rejection has a machine-readable reason plus human-readable explanation.

- [ ] **Step 2: Run quality tests and verify failure**

Run: `uv run pytest tests/unit/test_quality_pipeline.py tests/unit/test_similarity.py -q`

- [ ] **Step 3: Implement deterministic vector embeddings**

Hash normalized token unigrams and bigrams into a fixed 384-dimensional float vector, L2-normalize it, fingerprint the embedder name/version/dimensions, and compare vectors only when fingerprints match. Label this adapter `lexical-hash-v1`; keep optional local semantic and remote embedding adapters behind the same protocol.

- [ ] **Step 4: Implement explainable quality scoring**

Score structural validity as a hard gate, then completeness, useful length, instruction/response overlap, lexical richness, boilerplate, seed novelty, accepted-pool diversity, and configured constraints. Persist component scores, aggregate score, nearest-match ID/similarity, decision, and reason codes.

- [ ] **Step 5: Add human review overrides**

Allow `accept`, `reject`, and `needs_review` decisions with notes while retaining the original automated decision and score. Emit an audit event for each review.

- [ ] **Step 6: Run and commit the quality slice**

Run: `uv run pytest tests/unit/test_quality_pipeline.py tests/unit/test_similarity.py -q`

Run: `git add src/dataset_foundry/quality tests && git commit -m "feat: add explainable quality gates"`

### Task 5: Durable worker and generation orchestration

**Files:**
- Create: `src/dataset_foundry/jobs/queue.py`, `worker.py`, `recovery.py`
- Create: `src/dataset_foundry/generation/service.py`
- Test: `tests/integration/test_worker.py`, `tests/integration/test_generation_pipeline.py`

- [ ] **Step 1: Write end-to-end worker tests**

Create a dataset and recipe, enqueue a run, process it with the offline provider, and assert accepted/review/rejected counts reconcile. Test cancellation, bounded provider retry, candidate-cap exhaustion, lease expiry, worker recovery, and idempotent replay.

- [ ] **Step 2: Run worker tests and verify failure**

Run: `uv run pytest tests/integration/test_worker.py tests/integration/test_generation_pipeline.py -q`

- [ ] **Step 3: Implement SQLite job leases**

Claim one queued job atomically, heartbeat while a batch runs, fence writes by lease owner, requeue expired leases, and mark terminal jobs completed, failed, or cancelled. Use one writer worker by default and an explicit `--once` mode for deterministic tests.

- [ ] **Step 4: Implement the bounded generation loop**

Stratify seeds, request candidate batches, validate, score, persist every candidate and attempt, stop at the target count or candidate cap, and update run progress after each batch. Store the recipe, prompt, provider, model, embedder, and source fingerprints with the run.

- [ ] **Step 5: Prove recovery and deterministic replay**

Run: `uv run pytest tests/integration/test_worker.py tests/integration/test_generation_pipeline.py -q`

Expected: an expired job resumes without duplicate accepted candidates, and two offline runs with the same seed produce the same accepted fingerprints.

- [ ] **Step 6: Commit the worker slice**

Run: `git add src/dataset_foundry/jobs src/dataset_foundry/generation tests && git commit -m "feat: add durable generation worker"`

### Task 6: Immutable exports

**Files:**
- Create: `src/dataset_foundry/exports/service.py`, `formats.py`, `splits.py`, `manifest.py`
- Test: `tests/integration/test_exports.py`

- [ ] **Step 1: Write reload and hash tests**

Export one accepted run to canonical JSONL, OpenAI chat JSONL, Alpaca JSONL, and train/validation/test Parquet shards. Reload every format, assert counts, assert no lineage group crosses splits, and verify every SHA-256 entry in the manifest.

- [ ] **Step 2: Run export tests and verify failure**

Run: `uv run pytest tests/integration/test_exports.py -q`

- [ ] **Step 3: Implement grouped deterministic splitting**

Group by root seed lineage, shuffle groups with the recipe seed, and target `90/5/5` without splitting related families. Record actual ratios and counts rather than claiming exact ratios for tiny datasets.

- [ ] **Step 4: Write immutable artifacts atomically**

Write into a temporary sibling directory, hash each file, write `manifest.json` and `README.md` dataset card, then atomically rename to `.data/artifacts/<export-id>/`. Refuse to overwrite an existing completed export.

- [ ] **Step 5: Run tests and commit**

Run: `uv run pytest tests/integration/test_exports.py -q`

Run: `git add src/dataset_foundry/exports tests && git commit -m "feat: add immutable fine-tuning exports"`

### Task 7: FastAPI and CLI product surface

**Files:**
- Create: `src/dataset_foundry/api/app.py`, `routes/*.py`, `middleware.py`, `errors.py`
- Create: `src/dataset_foundry/cli.py`, `src/dataset_foundry/container.py`
- Test: `tests/integration/test_api_workflow.py`, `tests/unit/test_cli.py`

- [ ] **Step 1: Write the HTTP workflow test**

Exercise health → create project → upload seeds → create recipe → preflight → enqueue run → process one worker job → inspect candidates → review one candidate → export → download. Assert `201` for resources, `202` for queued work, typed problem responses for errors, and stable cursor pagination.

- [ ] **Step 2: Run API tests and verify failure**

Run: `uv run pytest tests/integration/test_api_workflow.py tests/unit/test_cli.py -q`

- [ ] **Step 3: Implement routes and operational endpoints**

Provide `/health`, `/ready`, `/metrics`, and `/api/v1` endpoints for projects, seeds, recipes, preflight, runs, run cancellation/events, candidates, reviews, exports/downloads, and provider status. Add request IDs, safe error envelopes, upload bounds, localhost-safe CORS, and optional API-key enforcement for non-loopback binding.

- [ ] **Step 4: Implement CLI commands**

Expose `serve`, `worker`, `demo`, `generate`, `export`, and `doctor`; make `demo` initialize the database, load the versioned support seeds, complete an offline run, and create an export without network access.

- [ ] **Step 5: Run API/CLI tests and commit**

Run: `uv run pytest tests/integration/test_api_workflow.py tests/unit/test_cli.py -q`

Run: `git add src/dataset_foundry/api src/dataset_foundry/cli.py src/dataset_foundry/container.py tests && git commit -m "feat: expose API and CLI workflows"`

### Task 8: React workbench

**Files:**
- Create: `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig*.json`
- Create: `frontend/src/api/*`, `frontend/src/components/*`, `frontend/src/features/*`
- Create: `frontend/src/App.tsx`, `frontend/src/main.tsx`, `frontend/src/styles/*.css`
- Test: `frontend/cypress/component/*.cy.tsx`, `frontend/tests/e2e/workbench.spec.ts`

- [ ] **Step 1: Create the shell and component tests**

Write Cypress component tests for navigation, status badges, metric cards, upload dropzone, generation preflight, review decision controls, error state, empty state, loading state, and details disclosure. Keep Cypress configured with `test:component: cypress run --component` only.

- [ ] **Step 2: Implement typed API access**

Use one `fetchJson<T>` client with request cancellation, timeout, JSON/problem parsing, and typed `ApiError`. Use TanStack Query with parallel independent overview queries, bounded polling only for active runs, and mutation-driven invalidation.

- [ ] **Step 3: Implement the familiar work-app workflow**

Build Overview, Projects, Generate, Runs, Review, Exports, and Settings views. The primary path is `Import seeds → Configure recipe → Preflight → Generate → Review quality → Export`; put raw prompts, fingerprints, provider traces, and component scores inside labeled `Details` disclosures.

- [ ] **Step 4: Implement a restrained responsive system**

Use neutral ink/sand surfaces with a teal operational accent, accessible focus-visible rings, reduced-motion support, 44px touch targets, mobile navigation, responsive tables/cards, and complete hover/selected/disabled/loading/error/empty states. Never show provider credentials in the browser.

- [ ] **Step 5: Add E2E workflow tests**

Configure Playwright exclusively under `frontend/tests/e2e/` with `test:e2e: playwright test`. Prove project creation, JSONL upload, offline generation, review, export download, details disclosure, console health, and desktop/tablet/mobile overflow.

- [ ] **Step 6: Build and commit the frontend**

Run: `npm run typecheck && npm run build && npm run test:component`

Expected: TypeScript, production build, and Cypress component tests pass.

Run: `git add frontend && git commit -m "feat: add Dataset Foundry workbench"`

### Task 9: Demo, scale, containers, CI, and security

**Files:**
- Create: `scripts/bootstrap_demo.py`, `scripts/benchmark_scale.py`
- Create: `Dockerfile`, `compose.yaml`, `.dockerignore`
- Create: `.github/workflows/ci.yml`, `SECURITY.md`, `CONTRIBUTING.md`
- Test: `tests/scale/test_offline_scale.py`, `tests/live/test_provider_smoke.py`

- [ ] **Step 1: Add scale and live-provider boundaries**

The default CI scale gate generates/scores/exports 250 candidates key-free. A separate local benchmark proves at least 2,000 candidates with peak-memory reporting. Live tests require an explicit flag, provider allowlist, maximum call count, approved seed hash, and matching credential presence; they never run in the default suite.

- [ ] **Step 2: Add hardened local containers**

Build frontend assets, install the locked Python wheel, run API and worker as non-root, bind ports to loopback, mount only `.data`, add health checks, and avoid embedding provider keys in images or compose files.

- [ ] **Step 3: Add CI quality gates**

Run Ruff format/check, strict mypy, pytest with branch coverage at least 80%, Bandit, pip-audit, package build/install smoke, frontend typecheck/build, Cypress component tests, Playwright E2E, and Compose config validation.

- [ ] **Step 4: Validate the offline release surface**

Run: `make check && make benchmark-ci && docker compose config --quiet`

Expected: all deterministic checks pass; live-provider and hosted proof remain explicitly unclaimed.

- [ ] **Step 5: Commit operations and CI**

Run: `git add scripts Dockerfile compose.yaml .dockerignore .github SECURITY.md CONTRIBUTING.md tests && git commit -m "build: add release and scale gates"`

### Task 10: Documentation, rendered proof, and handoff

**Files:**
- Create: `README.md`
- Create: `docs/getting-started.md`, `docs/architecture.md`, `docs/api.md`, `docs/generation-methodology.md`, `docs/quality-methodology.md`, `docs/operations.md`, `docs/security.md`, `docs/extending.md`, `docs/troubleshooting.md`
- Create: `docs/assets/dataset-foundry-overview.png`
- Create: `docs/dataset-foundry/2026-07-18-build-completion.md`
- Create: `docs/handoffs/2026-07-18-codex-dataset-foundry-complete.handoff.mdc`

- [ ] **Step 1: Write adopter documentation**

Lead with one promise: “Turn a small seed set into reviewable, fine-tuning-ready data.” Include the one-command offline demo, core workflow, provider setup, export contracts, quality math, cost/privacy controls, recovery behavior, extension points, and exact proof boundaries.

- [ ] **Step 2: Run the complete local workflow**

Run the demo bootstrap, API, worker, and frontend. Exercise the flow `Overview → project → run → review → export` using the in-app Browser, then run the committed Playwright E2E suite. Check page identity, meaningful content, error overlays, console errors/warnings, the main interaction, desktop/tablet/mobile layouts, keyboard focus, and reduced motion.

- [ ] **Step 3: Inspect and commit a sanitized screenshot**

Capture the completed overview with no credentials or private data, inspect it visually for clipping/blank/error states, and save the adopter-facing image at `docs/assets/dataset-foundry-overview.png`.

- [ ] **Step 4: Write completion evidence**

Record changed surfaces, commands and results, scale numbers, screenshot path, offline/demo data classification, mocked-provider status, live-provider status, localhost/browser status, hosted/deploy status, commit SHA, and remaining proof gaps in `docs/dataset-foundry/2026-07-18-build-completion.md`.

- [ ] **Step 5: Write the 12-section continuation handoff**

Follow `/Users/fortunevieyra/.codex/rules/post-chat-handoff.md` exactly and create the repo-local `.mdc` package with architecture, current state, decisions, recent work, validation, failure modes, processes, risks, artifacts, next work, continuation style, and confidence/freshness.

- [ ] **Step 6: Final audit, commit, and status proof**

Run: `make check && git status --short && git log -1 --oneline`

Expected: checks pass and only intentionally ignored runtime artifacts remain.

Run: `git add README.md docs && git commit -m "docs: complete Dataset Foundry handoff"`

## Self-review

- Spec coverage: seed import, thousands-scale generation, Pydantic structured output, OpenAI and Anthropic adapters, Parquet, quality scoring, vector similarity, review, fine-tuning formats, FastAPI, workbench, tests, security, and deployment assets each map to a task.
- Placeholder scan: the plan contains no unbounded implementation placeholders; optional adapters are explicitly outside the default runtime and share a defined protocol.
- Type consistency: `TrainingExample`, `GenerationRecipe`, `CandidateBatch`, `QualityReport`, `RunStatus`, and `ExportManifest` retain the same names and responsibilities across providers, worker, API, frontend, export, and tests.
- Proof boundaries: offline deterministic, mocked provider, live provider, localhost/browser, and hosted/deployed evidence remain separate.
