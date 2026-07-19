# Dataset Foundry open-source adoption completion

- Date: 2026-07-18 PDT
- Repository: `ownasquare/dataset-foundry`
- Public URL: https://github.com/ownasquare/dataset-foundry
- Implementation commit: `9405bdb56cf6d5b8f4dbc098195ac06abd30e2f3`

## Outcome

Dataset Foundry is ready to promote as a local-first open-source public beta. A new adopter can clone
the repository, run one Docker command, and reach a populated network-free workbench with a complete
seed-to-export example. The default interface now centers Import → Generate → Review → Export, while
Projects, Runs, and Settings remain available under progressive disclosure.

The repository is public on GitHub. Issues and Discussions are enabled, the wiki is disabled,
private vulnerability reporting is enabled, and repository topics identify the fine-tuning,
synthetic-data, FastAPI, LLM, and Parquet use cases.

## Adoption work completed

- Replaced the multi-process newcomer setup with `make quickstart`, backed by an idempotent offline
  bootstrap, API, and worker Compose stack.
- Made `dataset-foundry demo` reuse its completed run and export instead of duplicating data.
- Packaged the compiled React workbench inside the Python wheel and Docker image.
- Reduced primary navigation to Overview, Generate, Review, and Exports; moved operational views
  under **More**.
- Added actionable prerequisite and empty states, accessible information controls for advanced
  quality settings, functional run cancellation, and correct mobile drawer/focus behavior.
- Added persisted worker presence, `/api/v1/system/status`, worker-aware preflight, and explicit
  worker-offline guidance.
- Corrected run progress to measure accepted examples against the accepted target while retaining
  evaluated-candidate counts as secondary evidence.
- Prevented review notes from carrying onto another candidate.
- Added a public `CandidateScorer` contract and a `Container(quality_pipeline_factory=...)` hook
  proven through the durable worker.
- Added runnable input/scorer examples plus exact provider, embedder, ingestion, export, and React
  extension maps.
- Reworked README, getting-started, API, architecture, operations, extension, contribution,
  security, support, conduct, changelog, issue-form, and pull-request guidance for public adoption.
- Refreshed the README screenshot from the final packaged interface.

## First-use contract

```bash
git clone https://github.com/ownasquare/dataset-foundry.git
cd dataset-foundry
make quickstart
```

Expected result at `http://127.0.0.1:8765`:

- one Customer Support Demo project;
- one 12-row seed dataset;
- one completed offline run with 25 accepted and 1 rejected example;
- one immutable export package with canonical JSONL, OpenAI chat JSONL, Alpaca JSONL, and Parquet;
- API and worker both reported ready.

Running the bootstrap again leaves those totals unchanged and prints `Offline demo already ready`.

## Validation evidence

| Proof layer | Result |
|---|---|
| Final deterministic gate | `make check` passed: Ruff, formatting, strict mypy, build, wheel/sdist, 76 backend tests with 1 live test deselected, 83.94% coverage, and 10 Cypress component tests. |
| Browser E2E | `make e2e`: 7/7 Playwright tests passed across the complete workflow, themes, cancellation, help controls, desktop/tablet/mobile widths, and drawer accessibility. |
| Security | `make security`: Bandit passed and `pip-audit` found no known dependency vulnerabilities; the unpublished local package itself was correctly skipped as not present on PyPI. |
| Kernel benchmark | 250 candidates scored/exported at 237.87 examples/second, 242 accepted, 8 rejected, 8.53 MiB peak memory. |
| Durable benchmark | 250 accepted from 260 generated in 3.6855 seconds, 67.83 accepted examples/second, 12.22 MiB peak memory. |
| Container | `docker compose config --quiet` passed. A clean isolated named volume built and started bootstrap, API, and worker; both long-running services became healthy. |
| Container readback | `/api/v1/system/status` returned API ready, worker ready, and `idle`; overview returned 1 project, 1 dataset, 12 seeds, 25 accepted, 1 rejected, and 1 export. |
| Bootstrap replay | Compose bootstrap replay printed `Offline demo already ready` and did not change overview counts. |
| Wheel | A clean temporary virtual environment installed `dataset_foundry-0.1.0-py3-none-any.whl`; `doctor` reported built frontend assets and `demo` succeeded twice idempotently. |
| Packaged browser | The actual Docker-served bundle rendered meaningful desktop/mobile UI, `25 of 25 accepted · 26 evaluated`, 100% progress, singular copy, no horizontal overflow, and no console warnings/errors. |
| Independent review | Separate documentation and UI audits found no remaining P0/P1 adoption blockers after fixes. |
| GitHub publication | Public `main` initially matched implementation commit `9405bdb`; Issues, Discussions, topics, and private vulnerability reporting were verified through GitHub readback. |

## Proof boundaries and deliberate limitations

- Offline generation, mocked-provider contracts, local package, local container, local browser, and
  public source publication are proven independently.
- No paid OpenAI or Anthropic call was made in this adoption pass. Live-provider quality, current
  model access, billing, and external provider reliability remain unverified.
- The source repository is hosted, but the application itself is not deployed as a hosted service.
- The package is built locally but is not published to PyPI.
- No GitHub release or version tag was created; `main` is the supported pre-release source.
- The default operating posture remains SQLite, one recommended worker, and one host. Distributed
  queues, production identity, object storage, and multi-tenancy are explicitly outside this beta.
- When `DATASET_FOUNDRY_API_KEY` is enabled, the bundled browser does not collect that credential;
  non-loopback deployments need a trusted authentication proxy or an environment-specific UI auth
  integration.

## Remaining non-blocking backlog

- Add hash or route-based deep links so browser back/refresh can preserve the active workbench view.
- Replace raw automated reason-code strings with friendly labels and optional evidence help.
- Surface export-builder dependency failures at the exact project/run selector that caused them.
- Run bounded live-provider smoke tests only when an owner supplies credentials and approves cost
  and external seed transfer.
- Publish a signed/tagged release and PyPI artifact when the maintainer is ready to support a stable
  release channel.

These items are P2 or later for the local-first public beta and do not block cloning, installing,
running, understanding, or extending the current project.
