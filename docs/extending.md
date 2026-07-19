# Extending Dataset Foundry

## Generation providers

A provider accepts a bounded `GenerationBatchRequest` and returns `CandidateBatch`. It must:

- preserve the requested batch bound;
- return only canonical user/assistant or system/user/assistant messages;
- attach provider/model/prompt-version provenance;
- classify refusal, truncation, timeout, rate limit, and server errors;
- retry only transient errors within the recipe budget; and
- never read provider credentials in frontend code.

Register the adapter in the provider registry and add contract tests for success, refusal,
truncation, malformed business output, timeout, rate limit, and server error. Default tests must use
test doubles; paid calls belong behind the explicit `live` marker and budget guard.

## Embedders

An embedder returns normalized vectors plus an immutable fingerprint. Include algorithm/provider,
model, version, dimensions, and normalization settings in that fingerprint. The similarity service
must reject cross-fingerprint comparisons rather than producing a misleading cosine value.

Add fixtures immediately below and above the configured duplicate threshold, plus exact-duplicate
and empty-text cases.

## Ingestion formats

Map new formats into `TrainingExample` before persistence. Keep source-specific parsing outside the
domain model, enforce upload and row bounds, normalize deterministically, and prove equivalent
content from every supported format produces the same dataset fingerprint.

## Quality components

New components return a bounded score, pass/fail state, explanation, and stable reason code. Define
how missing evidence behaves; do not convert missing evidence to a failing zero. Keep structural and
duplicate hard gates explicit rather than hiding them inside a weighted score.

## Export formats

Write new files through the atomic export staging directory, add their SHA-256 and row count to the
manifest, then reload the artifact in an integration test. Export code must not modify completed
directories.

## Frontend views

Use the shared shell, tokens, and workbench components. Add loading, empty, error, disabled, hover,
selected, and focus-visible states. Cypress remains component-only; every end-to-end workflow goes
under Playwright.

