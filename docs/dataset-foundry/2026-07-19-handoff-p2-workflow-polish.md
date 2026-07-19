# Dataset Foundry P2 workflow polish completion

- Date: 2026-07-19 PDT
- Repository: `ownasquare/dataset-foundry`
- Public URL: https://github.com/ownasquare/dataset-foundry
- Implementation commit: `0671ff0460bafe30453796a8d8ca88bf00b14524`

## Outcome

The three remaining local P2 adoption items are complete. Dataset Foundry now keeps each workbench
view in a stable URL, explains quality findings in plain language without hiding evidence, and
guides users back to the exact project or run selector when an export dependency changes.

No new installation step or runtime dependency was introduced. The core newcomer flow remains:

```bash
git clone https://github.com/ownasquare/dataset-foundry.git
cd dataset-foundry
make quickstart
```

## What changed

- **Shareable workbench views:** Overview, Generate, Review, Exports, Projects, Runs, and Settings
  use `#overview`, `#generate`, `#review`, `#exports`, `#projects`, `#runs`, and `#settings`.
  Refresh, direct links, and browser back/forward preserve the active view.
- **Understandable quality findings:** reviewers see concise labels and stored evidence first. Raw
  reason codes remain available in an optional disclosure for audits and extensions. Unknown custom
  codes degrade to a readable label without changing the stored identifier.
- **Recoverable exports:** the API returns stable problem codes for missing, mismatched, incomplete,
  or empty project/run dependencies. The form places guidance beside the responsible selector,
  moves focus there, keeps unrelated inputs, and requires a valid correction instead of silently
  choosing another run.
- **Backward compatibility:** legacy reason arrays still ship, structured `quality_reasons` is
  additive, and export `project_id` is optional at the schema boundary.

## Validation evidence

| Proof layer | Result |
|---|---|
| Complete deterministic gate | `make check` passed: Ruff, format check, strict mypy, frontend build and typecheck, wheel/sdist build, 77 backend tests with 1 live test deselected, 84.38% coverage, and 23 Cypress component tests. |
| Browser E2E | `make e2e`: 9/9 Playwright workflows passed, including all seven direct hashes, reload, invalid-hash recovery, browser history, mobile navigation, quality evidence, and export recovery. |
| Security | `make security`: Bandit passed and `pip-audit` found no known dependency vulnerabilities; the unpublished local package was skipped because it is not on PyPI. |
| Benchmark | `make benchmark-ci`: 250 generated, 242 accepted, 8 rejected, 436.72 examples/second, 8.55 MiB peak memory, and 7 artifacts. |
| Container definition | `docker compose config --quiet` passed. |
| Rendered browser | The packaged demo was checked at 1440×900 and 390×844. Direct Review loading, evidence, raw-code disclosure, keyboard help, back/reload, and mobile drawer behavior worked with no overflow, framework overlay, console warning, or console error. |
| Independent review | A separate P0–P2 audit found no remaining actionable finding after the edge-case fixes. |

## Proof boundaries

- Deterministic offline behavior, mocked provider contracts, local packaging, local browser behavior,
  and public source are proven separately.
- No paid OpenAI or Anthropic request was made. Current model access, billing, rate limits, and live
  provider output remain unverified.
- The application is not deployed as a hosted service.
- No version tag, GitHub release, or PyPI package was created.
- Argilla and distilabel remain optional integrations, not core dependencies.

## Gated next moves

The next work requires an explicit maintainer or infrastructure decision:

- run one bounded live-provider smoke only after approving credentials, cost, model, and sanitized
  seed transfer;
- choose a compatibility and support policy before creating a tag, GitHub release, or PyPI channel;
- design authenticated shared storage, backups, retention, and observability before hosting beyond
  loopback;
- add Argilla or distilabel only when a real multi-reviewer or managed-annotation need is validated.

These external decisions do not block cloning, installing, understanding, extending, or completing
the local Import → Generate → Review → Export workflow.
