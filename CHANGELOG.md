# Changelog

All notable changes are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow semantic versioning.

## [Unreleased]

### Added

- One-command Docker quickstart with idempotent offline sample bootstrap.
- React workbench assets inside the Python wheel.
- Accessible inline explanations for advanced quality controls.
- Actionable first-run and prerequisite empty states.
- Functional run cancellation in the workbench.
- Public contributor, support, issue, pull-request, and conduct guidance.
- Injectable custom quality-scorer protocol and runnable example.
- Stable, refresh-safe URLs for all seven workbench views.
- Structured candidate quality reasons with readable labels, evidence, and raw-code disclosure.
- Stable RFC 7807 error codes and field locations for export dependencies.

### Changed

- Primary navigation now centers Generate, Review, and Exports while supporting views stay under
  progressive disclosure.
- The README now leads with first success, expected results, limitations, and extension paths.
- Export creation now preserves form input, focuses a stale project/run selector, and never silently
  substitutes another run after an explicit selection becomes invalid.

## [0.1.0] - 2026-07-18

### Added

- Local-first FastAPI, React, SQLite, and leased-worker synthetic-data workbench.
- Offline, OpenAI, and Anthropic structured generation adapters.
- Explainable quality scoring, vector similarity filtering, review history, and immutable exports.
- JSONL, OpenAI chat, Alpaca, and lineage-grouped Parquet output.
- Deterministic tests, scale benchmarks, packaging, containers, CI, security, and operations docs.

Release comparison links will be added with the first published tag.
