# Extending Dataset Foundry

Extensions should preserve the same product promises: strict schemas, bounded work, explicit
privacy, explainable decisions, immutable artifacts, and deterministic default tests.

## Add a quality scorer

This is the smallest extension because `QualityPipeline` accepts the public `CandidateScorer`
protocol and `Container` accepts a worker-facing pipeline factory. Start from
[`examples/custom_scorer.py`](../examples/custom_scorer.py):

```python
from dataset_foundry.domain import GeneratedCandidate, QualityComponent
from dataset_foundry.container import Container
from dataset_foundry.quality import QualityPipeline, ScoreResult, candidate_response


class PolicyScorer:
    def score(
        self,
        candidate: GeneratedCandidate,
        *,
        seed_similarity: float,
        accepted_similarity: float,
        constraints: list[str] | None = None,
    ) -> ScoreResult:
        del seed_similarity, accepted_similarity, constraints
        passed = "billing specialist" in candidate_response(candidate).casefold()
        component = QualityComponent(
            name="policy_grounding",
            score=1.0 if passed else 0.0,
            passed=passed,
            reason_code=None if passed else "missing_escalation_path",
            explanation="Checks the approved escalation phrase.",
        )
        return ScoreResult(score=component.score, components=(component,))


def build_quality_pipeline(
    *, quality_threshold: float, similarity_threshold: float
) -> QualityPipeline:
    return QualityPipeline(
        quality_threshold=quality_threshold,
        similarity_threshold=similarity_threshold,
        scorer=PolicyScorer(),
    )


container = Container(quality_pipeline_factory=build_quality_pipeline)
worker = container.worker()
```

`worker` now uses the custom scorer for persisted generation runs. The stock
`dataset-foundry worker` command intentionally uses the default factory; a deployment with custom
quality logic should create its worker from this injected `Container` in a small trusted entrypoint.
Both the API and custom worker must use the same database settings. Every component must return a
bounded score, pass/fail state, explanation, and stable failure reason code. A passing component may
use `None`. Do not convert missing evidence into a failing zero unless the contract explicitly
defines that behavior.

```bash
uv run python examples/custom_scorer.py
uv run pytest tests/unit/test_quality_pipeline.py -q
uv run pytest tests/integration/test_generation_pipeline.py -q
```

## Add a generation provider

Provider names are intentionally closed so a recipe cannot request an unregistered adapter.
Adding one is an explicit cross-stack change:

1. Add the identifier to `ProviderName` in `src/dataset_foundry/domain/models.py`.
2. Add server-side credential/model settings in `src/dataset_foundry/config.py`.
3. Implement `GenerationProvider` in `src/dataset_foundry/providers/<name>.py`.
4. Export and register construction/readiness in `providers/__init__.py` and `providers/registry.py`.
5. Add the provider to `ProviderKind` in `frontend/src/api/types.ts`, `MODEL_BY_PROVIDER` in
   `frontend/src/features/GenerateView.tsx`, and the deterministic demo status in
   `frontend/src/api/demo.ts`.
6. Add success/failure contract cases plus API and React provider-selection coverage.
7. Add an opt-in live smoke test with a strict request and cost bound.

The adapter shape is small:

```python
from dataset_foundry.domain import CandidateBatch, GenerationBatchRequest, ProviderName


class AcmeProvider:
    def __init__(self, model: str) -> None:
        self._model = model

    @property
    def name(self) -> ProviderName:
        return ProviderName.acme  # add this enum value first

    @property
    def model(self) -> str:
        return self._model

    async def generate_batch(self, request: GenerationBatchRequest) -> CandidateBatch:
        ...  # return exactly request.requested_count validated candidates
```

Before the provider SDK receives seed text, enforce external-transfer consent. Normalize model output
through server-owned provenance, reject unknown source seed IDs, classify refusal/truncation/rate
limit/timeout/server errors, and retry only transient errors within the recipe budget. Never read
credentials from frontend code and never fall back to another provider.

```bash
uv run pytest tests/contract/test_provider_contracts.py -q
uv run pytest tests/live/test_provider_smoke.py -m live -q  # explicit paid-call opt-in only
```

## Add an embedder

Implement `EmbeddingProvider` from `src/dataset_foundry/quality/embeddings.py` and pass the instance
to `QualityPipeline(embedder=...)` inside the same `Container(quality_pipeline_factory=...)` hook
shown above. Return normalized vectors plus an immutable fingerprint that includes
provider/algorithm, model, version, dimension, and normalization settings.

The similarity layer must reject cross-fingerprint comparisons. Add fixtures immediately below and
above the duplicate threshold, plus exact-duplicate and empty-text cases.

```bash
uv run pytest tests/unit/test_similarity.py tests/unit/test_quality_pipeline.py -q
```

## Add an ingestion shape

Map new input rows into `TrainingExample` in `src/dataset_foundry/ingestion/mapping.py`; keep
source-specific parsing in `loaders.py`. Preserve upload and row bounds, deterministic normalization,
duplicate reporting, and dataset fingerprints.

Prove that equivalent content from each supported shape produces the same fingerprint:

```bash
uv run pytest tests/unit/test_ingestion.py -q
```

## Add an export format

1. Add the enum value to `ExportFormat` in `src/dataset_foundry/domain/models.py`.
2. Add the row serializer in `src/dataset_foundry/exports/formats.py`.
3. Add dispatch, filename, and media-type handling in `src/dataset_foundry/exports/service.py`.
4. Add the frontend union and selectable format in `frontend/src/api/types.ts` and
   `frontend/src/features/ExportsView.tsx`.
5. Preserve row count, byte size, and SHA-256 evidence in the manifest.
6. Reload the artifact in `tests/integration/test_exports.py` and exercise it through the API/UI.

Completed export directories are immutable; never modify them in place.

```bash
uv run pytest tests/integration/test_exports.py -q
```

## Add a workbench view

Place feature views in `frontend/src/features/` and register them in `frontend/src/App.tsx`. Reuse the
shared shell, tokens, panels, fields, disclosures, and state components. Keep implementation details
behind progressive disclosure and give every empty state one clear next action.

Add loading, empty, error, disabled, hover, selected, focus-visible, desktop, and mobile coverage.
Cypress is component-only; Playwright owns E2E.

```bash
npm --prefix frontend run typecheck
npm --prefix frontend run test:component
npm --prefix frontend run test:e2e
```

## Before opening a pull request

```bash
make check
make benchmark-ci
make e2e
```

Update the nearest documentation and state clearly which proof layers were actually run.
