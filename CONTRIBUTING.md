# Contributing

## Development setup

```bash
uv sync --frozen
npm --prefix frontend ci
```

Run `make check` before opening a pull request. Backend tests must remain deterministic and
credential-free by default. Provider calls belong only in tests marked `live` and require an
explicit opt-in budget.

## Test ownership

- Pytest owns Python unit, integration, contract, and scale tests.
- Cypress owns React component tests under `frontend/cypress/component/` only.
- Playwright owns all end-to-end tests under `frontend/tests/e2e/`.

Never add Cypress end-to-end tests. Preserve offline, mocked-provider, live-provider, browser, and
hosted proof as separate evidence layers.

## Change design

Prefer focused modules and typed boundaries. New generation providers implement the provider
protocol; new similarity systems implement the embedder protocol and carry an immutable
fingerprint. Every automatic rejection must retain an explainable reason and remain reviewable.

