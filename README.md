# Dataset Foundry

Turn a small seed set into diverse, reviewable, fine-tuning-ready data.

Dataset Foundry is a local-first workbench for generating structured examples with an offline
provider, OpenAI, or Anthropic; filtering them with explainable quality and similarity checks; and
exporting immutable JSONL or Parquet datasets.

![Dataset Foundry workbench](docs/assets/dataset-foundry-overview.png)

## Try the complete product

With Docker running:

```bash
git clone https://github.com/ownasquare/dataset-foundry.git
cd dataset-foundry
make quickstart
```

Open [http://127.0.0.1:8765](http://127.0.0.1:8765). That one command builds the app, starts the API
and worker, and idempotently prepares a network-free sample project. No API key is needed.

```bash
make stop        # stop the app and keep its data
make reset-demo  # stop the app and delete its local Docker data
```

No `make` command? Run `docker compose up --build --wait` instead. See
[Getting started](docs/getting-started.md) for native development and live-provider setup.

## Your first useful result

The quickstart opens with **Customer Support Demo**, 25 accepted examples, and one ready export
package containing canonical JSONL, OpenAI chat JSONL, Alpaca JSONL, and Parquet artifacts.

1. Open **Review**, choose **Accepted**, and inspect one example with its source and quality evidence.
2. Open **Exports** and download the canonical JSONL, OpenAI chat JSONL, Alpaca JSONL, or Parquet file.
3. Open **Generate** when you are ready to import your own seed file and create another bounded run.

The included [`customer-support-seeds.jsonl`](examples/customer-support-seeds.jsonl) is a safe file
to use for a second walkthrough.

## The core workflow

| Stage | What you do | What Dataset Foundry protects |
|---|---|---|
| Import | Add representative JSONL, JSON, CSV, or Parquet seeds | Schema, upload, row, duplicate, and fingerprint checks |
| Generate | Pick a provider, target, and quality bounds | Cost/candidate preflight, explicit data-transfer consent, durable jobs |
| Review | Inspect accepted, borderline, and rejected examples | Source lineage, readable evidence, raw reason codes, similarity, preserved human overrides |
| Export | Choose a fine-tuning format and data split | Lineage-grouped splits, dataset card, manifest, byte counts, SHA-256 |

Operational views such as Projects, Runs, and Settings stay under **More** so the main workflow stays
focused. Technical thresholds use focusable information controls, while cost, privacy, and errors
remain visible.

## Provider modes

| Provider | Best for | Network | Structured output |
|---|---|---:|---|
| `offline` | evaluation, CI, air-gapped work, and repeatable baselines | No | Local Pydantic objects |
| `openai` | live synthetic generation | Yes | Responses API with Pydantic parsing |
| `anthropic` | live synthetic generation | Yes | Messages API with Pydantic parsing |

Live runs require a server-side credential plus explicit external-data-transfer approval. Dataset
Foundry never silently replaces a selected paid provider with offline output.

## Install from source

The Docker quickstart is the supported first-run path. Contributors can run the processes directly:

```bash
make setup
uv run dataset-foundry demo
uv run dataset-foundry serve
```

Run `uv run dataset-foundry worker` in a second terminal. The built wheel includes the React
workbench; `make build` refreshes the packaged UI before creating the wheel and source archive.

## Extend it

| Extension | Start here | Registration or injection point |
|---|---|---|
| Generation provider | `src/dataset_foundry/providers/base.py` | `providers/registry.py` |
| Quality scorer | `src/dataset_foundry/quality/scorers.py` | `Container(quality_pipeline_factory=...)` |
| Embedder | `src/dataset_foundry/quality/embeddings.py` | same worker-facing pipeline factory |
| Input shape | `src/dataset_foundry/ingestion/mapping.py` | ingestion loader mapping |
| Export format | `src/dataset_foundry/exports/formats.py` | export service + manifest |
| Workbench view | `frontend/src/features/` | `frontend/src/App.tsx` |

[Extending Dataset Foundry](docs/extending.md) contains copyable scorer code, exact file paths, and
focused validation commands. [Contributing](CONTRIBUTING.md) explains the 10-minute contributor path.

## Good fit / not yet

Dataset Foundry is a good fit for local data teams, portfolio evaluation, offline baselines, and
single-host generation jobs. It is intentionally not yet a distributed multi-tenant service: the
default database is SQLite, one worker is recommended, and hosted authentication/object storage are
deployment-specific work.

## Validation

```bash
make check
make benchmark-ci
make e2e
```

Pytest owns Python tests, Cypress owns React component tests only, and Playwright owns all E2E tests.
Live-provider, local-browser, container, package, hosted, and deployed proof remain separate claims.

## Documentation

- [Getting started](docs/getting-started.md)
- [Architecture](docs/architecture.md)
- [Generation methodology](docs/generation-methodology.md)
- [Quality methodology](docs/quality-methodology.md)
- [API reference](docs/api.md)
- [Operations](docs/operations.md)
- [Security model](docs/security.md)
- [Extending Dataset Foundry](docs/extending.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Support](SUPPORT.md)
- [Changelog](CHANGELOG.md)

## License

MIT
