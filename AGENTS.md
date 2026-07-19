# Dataset Foundry agent guide

Follow `/Users/fortunevieyra/AGENTS.md` first. This file adds repository-specific constraints.

## Product contract

- Keep the default experience a familiar data workbench: projects, seed datasets, recipes, runs,
  review, and exports.
- Keep provider prompts, request traces, hashes, embedding fingerprints, and component internals
  behind progressive disclosure.
- Preserve offline, mocked-provider, live-provider, local-browser, hosted, and deployed proof as
  separate evidence layers.
- Never silently fall back from OpenAI or Anthropic to the deterministic provider.
- Never delete rejected candidates or rewrite an automated decision when a human review changes the
  effective decision.

## Architecture

- FastAPI is the only product data boundary. The frontend must not open SQLite, Parquet, artifact
  paths, or provider SDKs directly.
- Heavy generation runs in the leased worker, not FastAPI `BackgroundTasks`.
- Domain contracts use Pydantic with `extra="forbid"`.
- Compare vectors only when their embedder fingerprints match.
- Write exports through staging and atomic promotion; never overwrite a completed export.

## Tests

- Pytest owns Python unit, integration, contract, scale, and opt-in live tests.
- Cypress is exclusively for React component testing under `frontend/cypress/component/`.
- Playwright is exclusively for E2E under `frontend/tests/e2e/`.
- Maintain `"test:component": "cypress run --component"` and
  `"test:e2e": "playwright test"` in `frontend/package.json`.
- Default tests and CI must be deterministic and credential-free.

## Commands

```bash
uv sync --frozen
npm --prefix frontend ci
make check
make benchmark-ci
make e2e
```

Agent-authored shell commands beneath this home directory must use
`/Users/fortunevieyra/.codex/bin/codex-secret-safe-exec.py` and must never enumerate environment
values. Provider credentials remain server-side and must not be printed, persisted, or included in
fixtures.

## Completion

Update `docs/dataset-foundry/*.md` with current validation and proof boundaries. Create or refresh
the required 12-section `.mdc` package under `docs/handoffs/` before compaction and at completed-chat
handoff.
