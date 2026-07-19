# Open-Source Adoption Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Dataset Foundry understandable, runnable, and safely extensible for a first-time open-source adopter without obscuring its seed-to-export workflow.

**Architecture:** Preserve FastAPI as the sole product data boundary and the separate leased worker while adding a newcomer-oriented startup path, a progressive-disclosure React workflow, and public-maintainer documentation. Keep offline, live-provider, local-browser, package, container, hosted, and GitHub-release proof separate.

**Tech Stack:** Python 3.11+, FastAPI, Typer, React 19, TypeScript, TanStack Query, Docker Compose, Pytest, Cypress component tests, and Playwright E2E tests.

---

## Task 1: Capture the first-time-adopter baseline

- [x] Audit `README.md`, `docs/getting-started.md`, `docs/extending.md`, `CONTRIBUTING.md`, `compose.yaml`, `Makefile`, and `.github/` for missing or ambiguous public-repository guidance.
- [x] Exercise the documented clean startup path and record every command, prerequisite, hidden second process, and first useful result.
- [x] Exercise the rendered core flow: repository start → sample seeds → generation → review → export.
- [x] Convert confirmed gaps into explicit acceptance checks before implementation.

## Task 2: Add a genuinely simple startup and sample path

- [x] Add failing CLI/container tests for an idempotent offline bootstrap and a startup path that launches both API and worker responsibilities without silently changing provider mode.
- [x] Update `src/dataset_foundry/cli.py`, `compose.yaml`, `Makefile`, and focused test files so one documented command reaches a populated local workbench.
- [x] Keep advanced source-development commands available in `docs/getting-started.md`, but make the default README path short and key-free.
- [x] Verify the clean Docker path and the source path independently.

## Task 3: Center the product on Import → Generate → Review → Export

- [x] Add failing Cypress component tests and Playwright workflow assertions for the newcomer navigation, empty state, and concise help affordances.
- [x] Update `frontend/src/components/`, `frontend/src/features/`, and shared styles to make the four core stages primary and move operational/system details behind secondary navigation or disclosures.
- [x] Add accessible information buttons with click/focus help where a term needs explanation; do not rely on hover-only tooltips or use them for required instructions.
- [x] Ensure primary calls to action lead to the next incomplete workflow step and remain clear at desktop and mobile widths.

## Task 4: Make the public repository self-explanatory and maintainable

- [x] Rewrite the top of `README.md` around who the tool is for, the one-command demo, the four-step workflow, and a short extension map.
- [x] Add concise maintainer/release files under `.github/` plus `CODE_OF_CONDUCT.md`, `SUPPORT.md`, and `CHANGELOG.md` where the audit confirms they are missing.
- [x] Expand `docs/extending.md` with exact module paths, the smallest working provider/scorer/export examples, and the test contract for each extension type.
- [x] Check every local Markdown link and keep detailed internals in linked guides rather than the landing page.

## Task 5: Validate, independently review, and close out

- [x] Run focused tests while editing, then `make check`, `make benchmark-ci`, Cypress component tests, and Playwright E2E tests.
- [x] Build/install the wheel in a clean environment and run the Docker Compose newcomer path from a clean named volume.
- [x] Use the in-app browser for desktop and mobile screenshots, interaction proof, page identity, nonblank rendering, accessibility state, and console health.
- [x] Run an independent adoption review and resolve all P0–P2 issues that are in local scope.
- [ ] Update `docs/dataset-foundry/` with exact proof boundaries, create the required 12-section `.mdc` handoff, commit the validated repository, and publish the new public repository to `ownasquare/dataset-foundry`.
