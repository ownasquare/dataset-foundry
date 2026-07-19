# Getting started

Dataset Foundry includes an offline deterministic provider, so the complete seed-to-export workflow
can be evaluated without an API key.

## Prerequisites

- Python 3.11 or newer
- uv
- Node.js 20 or newer for frontend development
- Docker Desktop or another Compose-compatible runtime only for the container path

## Install

```bash
uv sync --frozen
npm --prefix frontend ci
npm --prefix frontend run build
```

Copy `.env.example` to `.env` only when local settings need to change. Do not commit `.env` or put
provider keys in any `VITE_` variable; browser-prefixed environment values are public.

## One-command offline demo

```bash
uv run dataset-foundry demo
```

The frontend build creates the assets served at port 8765. The demo initializes the local database,
imports the versioned customer-support seed set, completes
a deterministic run, and creates a fine-tuning export. It does not call OpenAI or Anthropic.

Start the workbench:

```bash
uv run dataset-foundry serve
```

Open `http://127.0.0.1:8765`. In a separate terminal, start a continuous worker when creating new
runs:

```bash
uv run dataset-foundry worker
```

For frontend development with hot reload, run `npm --prefix frontend run dev` and use the Vite URL;
the development server proxies `/api` to the local FastAPI service.

## Core workflow

1. Create or open a project.
2. Import a seed file using one of the supported shapes.
3. Create a recipe and inspect its privacy/cost preflight.
4. Generate with `offline` or an explicitly configured live provider.
5. Review near-threshold and rejected candidates with their reasons.
6. Export the effective accepted set.

## Live providers

Set only the provider credential needed by the server and keep model IDs configurable:

```bash
OPENAI_API_KEY=... uv run dataset-foundry serve
```

```bash
ANTHROPIC_API_KEY=... uv run dataset-foundry serve
```

The UI will still require explicit external-data-transfer approval for each live-provider run.
Provider credentials never belong in recipes, API request bodies, or the browser.

## Verify the installation

```bash
uv run dataset-foundry doctor
make check
```

`doctor` reports configuration and writable storage status using key-name-only provider readiness;
it never prints credential values. `make check` runs deterministic backend and frontend validation.
