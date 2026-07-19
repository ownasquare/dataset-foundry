# Getting started

The fastest path is fully offline and does not require a provider account.

## Docker quickstart

Prerequisites: Docker Desktop or another Compose-compatible runtime, plus `make`.

```bash
make quickstart
```

Open `http://127.0.0.1:8765`. The command builds the locked app, starts the API and worker, and
idempotently creates:

- the **Customer Support Demo** project;
- the versioned customer-support seed dataset;
- a completed 25-example offline generation; and
- canonical, OpenAI chat, Alpaca, and Parquet exports.

The bootstrap is safe to run again; it reuses the completed demo export instead of duplicating it.

```bash
make stop
```

`make stop` preserves the named data volume. `make reset-demo` deletes that volume and all local
Docker demo data, so use it only when a clean workspace is intended.

## Five-minute product tour

1. On **Overview**, confirm that Customer Support Demo has 25 accepted examples.
2. Open **Review**, select the **Accepted** filter, and inspect source and quality evidence.
3. Open **Exports** and download one fine-tuning artifact.
4. Open **Generate**, keep the offline provider selected, import
   `examples/customer-support-seeds.jsonl`, and run the preflight before generating.

Projects, Runs, and Settings are available under **More**. They are supporting views, not required
to understand the seed → generate → review → export path.

Every workbench view has a stable, refresh-safe URL. Add one of these hashes to the app URL when
sharing or bookmarking a starting point: `#overview`, `#generate`, `#review`, `#exports`,
`#projects`, `#runs`, or `#settings`. Browser back and forward keep the visible view in sync. IDs,
review notes, provider settings, and unfinished form values are intentionally not stored in the URL.

## Native contributor setup

Prerequisites: Python 3.11 or newer, [uv](https://docs.astral.sh/uv/), Node.js 20 or newer, and npm.

```bash
make setup
uv run dataset-foundry demo
uv run dataset-foundry serve
```

Open `http://127.0.0.1:8765`. Start the durable worker in a second terminal:

```bash
uv run dataset-foundry worker
```

The API and worker remain separate processes so generation never runs inside the HTTP request
lifecycle. For React hot reload, use `npm --prefix frontend run dev`; Vite proxies `/api` to the API.

## Wheel contract

`make build` refreshes the React assets and then creates the wheel and source archive. The packaged
wheel contains the workbench under `dataset_foundry/static`, so a wheel install is not API-only.
Dataset Foundry is not published to PyPI yet; build/install from the repository until a public
release exists.

## Use a live provider

Copy `.env.example` to `.env`, set exactly the provider key you intend to use, and keep that file out
of version control. Both the API and worker load the same `.env`; provider credentials remain
server-side and must never appear in a `VITE_` variable.

```bash
uv run dataset-foundry serve
```

```bash
uv run dataset-foundry worker
```

The workbench still requires explicit external-data-transfer approval for each live-provider recipe.
Provider credentials are never stored in recipes, sent in API request bodies, or returned to the
browser. Compose also reads the repository `.env` and passes only those two provider variables to
the API and worker; the sample bootstrap itself always stays offline.

## Verify the installation

```bash
uv run dataset-foundry doctor
make check
```

`doctor` reports configuration and writable storage using key-name-only readiness; it never prints
credential values. `make check` is deterministic and does not call paid providers.
