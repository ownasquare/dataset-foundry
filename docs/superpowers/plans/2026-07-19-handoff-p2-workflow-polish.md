# Dataset Foundry Handoff P2 Workflow Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the three local P2 handoff items by adding durable view URLs, understandable quality findings with preserved evidence, and field-specific export dependency recovery.

**Architecture:** Keep the workbench dependency-free at the navigation layer with a canonical hash map and one React hook. Extend the existing candidate API additively with structured quality reasons derived from already-persisted code/evidence arrays. Extend RFC 7807 problems with stable codes so the export form can focus and explain the exact failed selector while retaining FastAPI as the source of truth.

**Tech Stack:** React 19, TypeScript, TanStack Query, FastAPI, Pydantic v2, Cypress component testing, Playwright E2E, Python/pytest.

---

## File map

- Create `frontend/src/navigation.ts`: canonical view/hash map, parser, URL mutation, and history subscription hook.
- Modify `frontend/src/App.tsx`: route every internal destination through the URL-aware navigation callback.
- Modify `frontend/src/components/AppShell.tsx`: synchronize mobile drawer and secondary-navigation disclosure when history changes the active view.
- Create `frontend/cypress/component/navigation.cy.tsx`: component coverage for hashes, invalid input, and history-driven state.
- Modify `frontend/tests/e2e/workbench.spec.ts`: direct-link, refresh, back/forward, mobile drawer, quality reason, and export recovery proof.
- Modify `src/dataset_foundry/api/schemas.py`: additive `QualityReasonView`, `CandidateView.quality_reasons`, and backward-compatible optional `ExportCreate.project_id` contracts.
- Modify `src/dataset_foundry/api/routes/core.py`: construct structured quality reasons and emit stable export problem codes.
- Modify `src/dataset_foundry/api/errors.py`: add a stable `code` to RFC 7807 problem responses.
- Modify `src/dataset_foundry/api/middleware.py`: add the stable API-key problem code.
- Modify `frontend/src/api/types.ts`: add `CandidateReason` and replace UI-only raw-code arrays with structured reasons.
- Modify `frontend/src/api/client.ts`: parse structured reasons with legacy-array fallback and retain `ApiError.code`.
- Modify `frontend/src/api/demo.ts`: provide realistic reason evidence in deterministic demo candidates.
- Create `frontend/src/components/qualityReasonPresentation.ts`: known label map and safe unknown-code humanizer.
- Create `frontend/src/components/QualityReasonList.tsx`: visible labels/evidence, accessible optional help, and raw-code disclosure.
- Modify `frontend/src/features/ReviewView.tsx`: render the structured findings and humanize component labels.
- Modify `frontend/src/features/ExportsView.tsx`: preserve stale selections, localize failures, focus the affected selector, and avoid silent fallback.
- Modify `frontend/src/styles/base.css` and `frontend/src/styles/components.css`: invalid-control and findings presentation using existing tokens.
- Modify `frontend/cypress/component/workbench.cy.tsx`: friendly/unknown quality reasons and export field recovery.
- Modify `tests/integration/test_api_workflow.py`: structured quality reasons and stable problem-code assertions.
- Modify `docs/api.md`, `docs/quality-methodology.md`, `docs/getting-started.md`, and `CHANGELOG.md`: public contracts and current behavior.
- Regenerate `src/dataset_foundry/static/`: packaged workbench build.
- Create `docs/dataset-foundry/2026-07-19-handoff-p2-workflow-polish.md`: completion evidence and proof boundaries.
- Refresh the canonical and repository handoff records before completion.

### Task 1: Add stable workbench URLs

- [x] **Step 1: Write failing component and E2E assertions**

Add component assertions that `Review` produces `#review`, an explicit `#exports` load renders Exports, a dispatched history event restores the prior view, and `#unknown` is replaced with `#overview`. Add Playwright assertions for all seven direct hashes, refresh retention, back/forward, invalid-hash normalization, and mobile drawer closure after history navigation.

- [x] **Step 2: Run the focused tests and confirm the current state-only navigation fails**

Run: `npm --prefix frontend run test:component -- --spec cypress/component/navigation.cy.tsx`

Expected before implementation: the URL assertions fail because `App.tsx` stores only `activeView` React state.

- [x] **Step 3: Implement the canonical URL contract**

Create a single `VIEW_HASHES` map for `overview`, `generate`, `review`, `exports`, `projects`, `runs`, and `settings`. The hook must initialize from `initialView` when explicitly supplied, otherwise parse `window.location.hash`; normalize an empty or invalid hash with `history.replaceState`; use `history.pushState` for user navigation; preserve `?demo=1`; listen to `popstate` and `hashchange`; and never serialize IDs, notes, provider settings, or form data.

Replace every direct `setActiveView` callback in `App.tsx` with `navigateTo`. In `AppShell`, close the mobile drawer whenever `activeView` changes and collapse More when the new view is primary.

- [x] **Step 4: Run focused URL tests**

Run: `npm --prefix frontend run typecheck`

Run: `npm --prefix frontend run test:component -- --spec cypress/component/navigation.cy.tsx`

Expected: typecheck passes and every hash/history component assertion passes.

### Task 2: Present friendly quality findings without losing raw evidence

- [x] **Step 1: Write failing API and component assertions**

Extend the API workflow test to assert that each candidate returns both legacy `reason_codes`/`explanations` and additive `quality_reasons: [{"code": ..., "evidence": ...}]`. Extend Cypress coverage with one known core code, one demo code, one unknown custom code, and one missing-evidence code. Assert that friendly labels and evidence are visible, raw codes are hidden until the native disclosure opens, and optional help works by keyboard and Escape.

- [x] **Step 2: Verify the frontend currently drops persisted evidence**

Run: `uv run pytest tests/integration/test_api_workflow.py -q`

Run: `npm --prefix frontend run test:component -- --spec cypress/component/workbench.cy.tsx`

Expected before implementation: additive API and friendly-evidence assertions fail.

- [x] **Step 3: Add the structured reason contract and presentation**

Add `QualityReasonView(code: str, evidence: str | None)` to the API schema. In `_candidate_view`, pair each persisted reason code with its same-index explanation; when absent, fall back to the matching component `reason_code` explanation, then `None`. Keep the existing arrays unchanged for compatibility.

In TypeScript, use `CandidateReason { code: string; evidence: string | null }`. Parse `quality_reasons` first and fall back to legacy arrays/components for older API payloads. Map the eleven core and three demo codes to concise labels. Humanize unknown snake, kebab, uppercase, or camel identifiers without changing the stored code. Render visible labels and persisted evidence in a semantic list, use one accessible `InfoTip` for optional interpretation guidance, and put unchanged raw codes in a native `Disclosure`. Humanize score component identifiers only at presentation time.

- [x] **Step 4: Run focused quality tests**

Run: `uv run pytest tests/unit/test_quality_pipeline.py tests/integration/test_api_workflow.py -q`

Run: `npm --prefix frontend run typecheck`

Run: `npm --prefix frontend run test:component -- --spec cypress/component/workbench.cy.tsx`

Expected: codes/evidence remain ordered, custom codes survive, friendly labels render, missing evidence has an honest fallback, and raw identifiers remain accessible.

### Task 3: Localize export dependency failures

- [x] **Step 1: Write failing server and component assertions**

Assert the API returns `export_project_not_found`, `export_run_not_found`, `export_run_project_mismatch`, `export_run_not_complete`, and `export_run_has_no_accepted_examples` with field locations. In Cypress, keep an explicitly selected stale run unresolved instead of silently selecting the first eligible run; assert `aria-invalid`, `aria-describedby`, exact helper text, and focus on the Completed run selector after the server rejects it. Add a no-project state assertion on the Project selector.

- [x] **Step 2: Confirm current errors are generic and stale runs silently fall back**

Run: `uv run pytest tests/integration/test_api_workflow.py -q`

Run: `npm --prefix frontend run test:component -- --spec cypress/component/workbench.cy.tsx`

Expected before implementation: server codes are `request_failed`/absent and stale selection resolves to another run.

- [x] **Step 3: Implement stable problem codes and selector recovery**

Add code/field-issue support to `ApiProblem` and include a stable code in every RFC 7807 body. Add optional `project_id` to the export payload, send it from the frontend, and validate project existence plus run/project ownership before export. Emit the five stable export dependency codes from the route while preserving request IDs and legacy titles/details.

In `ExportsView`, distinguish an untouched empty selection from an explicitly stale project/run. Never fall back after an explicit ID becomes invalid. Derive project/run dependency messages beside their controls; set `aria-invalid` and `aria-describedby`; classify `ApiError.code`; focus the affected selector after a failed mutation; refetch project/run options after a stale server response; and keep valid form values intact for retry. Show form-level errors only when no selector owns the failure.

- [x] **Step 4: Run focused export tests**

Run: `uv run pytest tests/integration/test_api_workflow.py -q`

Run: `npm --prefix frontend run typecheck`

Run: `npm --prefix frontend run test:component -- --spec cypress/component/workbench.cy.tsx`

Expected: stable server codes, no silent run substitution, correct focus/readback, and successful retry behavior.

### Task 4: Regenerate, validate, and visually prove the integrated workflow

- [x] **Step 1: Build the packaged workbench**

Run: `npm --prefix frontend run build`

Expected: `src/dataset_foundry/static/index.html` and hashed assets are regenerated without source maps.

- [x] **Step 2: Run deterministic and browser gates**

Run: `make check`

Run: `make e2e`

Run: `make security`

Expected: lint, format, strict mypy, backend coverage, build/package, Cypress components, all Playwright workflows, Bandit, and dependency audit pass.

- [x] **Step 3: Run real rendered-browser validation**

The flow under test is: direct `#review` load → inspect friendly finding and raw-code disclosure → navigate/back/refresh → open Exports → reproduce a selector dependency correction → create a valid export.

Use the in-app Browser first. Verify page identity, meaningful DOM, no framework overlay, console warnings/errors, screenshot evidence, keyboard/touch help behavior, desktop 1440×900, and mobile 390×844 with no horizontal overflow.

- [x] **Step 4: Run an independent P0–P2 review**

Have a separate agent inspect only the changed contracts and rendered behavior. Resolve every in-scope P0–P2 issue before publication.

### Task 5: Document and publish the completed continuation

- [ ] **Step 1: Update public documentation and the dated completion record**

Document the seven hashes, additive `quality_reasons`, raw-code compatibility, stable problem codes, selector recovery, exact validation, and the unchanged external boundaries. Update `CHANGELOG.md` under Unreleased.

- [ ] **Step 2: Refresh continuation artifacts**

Create or refresh the canonical 12-section handoff at `/Users/fortunevieyra/Documents/Github/beladed.com/docs/handoffs/2026-07-19-codex-dataset-foundry-p2-workflow-polish.handoff.mdc`, link it under `docs/handoffs/`, and create the required Beladed documentation record without touching Beladed runtime source.

- [ ] **Step 3: Commit and publish intentionally**

Run: `git diff --check`

Run: `git status --short`

Commit the validated implementation and documentation, push `main` to `ownasquare/dataset-foundry`, verify local/remote SHA equality, and wait for the final GitHub Actions run to pass.

- [ ] **Step 4: Record gated next moves truthfully**

Keep live paid-provider smoke, a supported tag/PyPI release, hosted authenticated infrastructure, and optional Argilla/distilabel integration as separate owner-decision items. Do not infer authorization from completion of these local P2 improvements.
