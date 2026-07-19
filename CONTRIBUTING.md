# Contributing

Thanks for helping Dataset Foundry make synthetic training data easier to create and trust.

## Ten-minute setup

```bash
make setup
uv run dataset-foundry demo --target-count 5
uv run dataset-foundry serve
```

Open `http://127.0.0.1:8765`. Start `uv run dataset-foundry worker` in a second terminal when testing
queued runs. The offline provider is deterministic and key-free; use it for normal development.

## Repository map

| Area | Path |
|---|---|
| API and schemas | `src/dataset_foundry/api/` |
| Domain contracts | `src/dataset_foundry/domain/` |
| Providers | `src/dataset_foundry/providers/` |
| Quality and similarity | `src/dataset_foundry/quality/` |
| Durable worker and queue | `src/dataset_foundry/jobs/` |
| React workbench | `frontend/src/` |
| Python tests | `tests/` |
| Browser/component tests | `frontend/tests/e2e/`, `frontend/cypress/component/` |

Read [Architecture](docs/architecture.md) before changing boundaries and
[Extending Dataset Foundry](docs/extending.md) for extension-specific contracts.

## Focused checks

```bash
make test-unit
make test-integration
npm --prefix frontend run typecheck
npm --prefix frontend run test:component
```

Before opening a pull request:

```bash
make check
make benchmark-ci
make e2e
```

`make format` applies Python formatting. Keep frontend formatting consistent with nearby source.

## Test ownership

- Pytest owns Python unit, integration, contract, scale, and opt-in live tests.
- Cypress owns React component tests under `frontend/cypress/component/` only.
- Playwright owns all end-to-end tests under `frontend/tests/e2e/`.

Never add Cypress E2E tests. Default tests must stay deterministic, credential-free, and free of paid
provider calls. Live calls require the `live` marker, explicit credentials, and a bounded budget.

## Change expectations

- Open or reference an issue for behavior changes that affect public contracts.
- Keep pull requests focused and include tests for failure paths as well as success paths.
- Preserve offline, mocked-provider, live-provider, browser, container, package, hosted, and deployed
  proof as separate claims.
- Never silently fall back between providers or expose provider secrets to the browser.
- Keep automatic decisions explainable and preserve human-review history.
- Update the nearest user or maintainer documentation when behavior changes.

Use the pull-request template as the final checklist. By participating, you agree to the
[Code of Conduct](CODE_OF_CONDUCT.md).
