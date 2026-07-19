# API reference

Interactive OpenAPI documentation is available at `http://127.0.0.1:8765/docs` while the API is
running; the machine-readable schema is at `/openapi.json`.

Safe sample inputs are available in `examples/` for canonical chat JSONL, Alpaca JSONL,
prompt/completion CSV, and customer-support instruction/output JSONL.

The API is versioned beneath `/api/v1`. JSON timestamps use ISO-8601 UTC. Cursor collections return
`{"items": [...], "next_cursor": "..."}`; `next_cursor` is `null` on the final page.

## Authentication

Loopback development is key-free by default. When `DATASET_FOUNDRY_API_KEY` is set, `/api/*`, API
documentation, the OpenAPI schema, and `/metrics` require the same value in the `X-API-Key` header.
The bundled workbench does not collect or store that credential; non-loopback deployments should
put a trusted authentication proxy in front of the app or provide an environment-specific UI auth
integration.

## Operations

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Process liveness. |
| `GET` | `/ready` | Database and startup readiness. |
| `GET` | `/metrics` | Small operational counter snapshot. |
| `GET` | `/api/v1/system/status` | API and persisted worker-heartbeat readiness. |
| `GET` | `/api/v1/overview` | Project, dataset, run, candidate, and export totals. |
| `GET` | `/api/v1/providers` | Provider capability/configuration status without credentials. |

## Projects and seeds

| Method | Path | Result |
|---|---|---|
| `POST` | `/api/v1/projects` | Creates a project from `name` and optional `description`. |
| `GET` | `/api/v1/projects` | Lists projects with cursor pagination. |
| `POST` | `/api/v1/projects/{project_id}/seeds` | Imports a multipart `file`. |
| `GET` | `/api/v1/projects/{project_id}/datasets` | Lists normalized seed datasets. |

Seed imports accept JSON, JSONL, CSV, and Parquet using one of these source shapes:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

```json
{"instruction":"...","input":"...","output":"..."}
```

```json
{"prompt":"...","completion":"..."}
```

## Recipes and preflight

`POST /api/v1/projects/{project_id}/recipes` creates the bounded generation contract.

```json
{
  "name": "Support expansion v1",
  "target_count": 1000,
  "batch_size": 20,
  "candidate_multiplier": 3,
  "min_quality_score": 0.72,
  "max_similarity": 0.92,
  "seed": 42,
  "constraints": ["Keep responses actionable", "Do not invent account actions"]
}
```

`POST /api/v1/recipes/{recipe_id}/preflight` accepts the dataset, provider, optional model, and
external-transfer consent. It returns `ready`, budgets, transfer requirements, and explicit
`blockers`. It also returns `worker_ready`; a caller should not enqueue a run unless both the
recipe/provider checks and a current worker heartbeat are ready.

`GET /api/v1/system/status` distinguishes API readiness from worker readiness. Its worker state is
`idle`, `busy`, `stale`, `stopped`, or `missing`, with the latest worker ID and heartbeat timestamps
when available. This lets clients explain why a queued run cannot make progress without exposing
credentials or process internals.

## Runs

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/runs` | Persists a queued run and returns `202`. |
| `GET` | `/api/v1/runs` | Lists runs. |
| `GET` | `/api/v1/runs/{run_id}` | Reads current progress and reconciled counts. |
| `POST` | `/api/v1/runs/{run_id}/cancel` | Requests cancellation for a non-terminal run. |
| `GET` | `/api/v1/runs/{run_id}/events` | Reads state-change evidence. |
| `GET` | `/api/v1/runs/{run_id}/candidates` | Lists candidates, optionally filtered by decision. |

Create-run payload:

```json
{
  "project_id": "project-id",
  "dataset_id": "dataset-id",
  "recipe_id": "recipe-id",
  "provider": "offline",
  "allow_external_data_transfer": false
}
```

## Review

`POST /api/v1/candidates/{candidate_id}/reviews` preserves an override without deleting automated
evidence:

```json
{
  "decision": "accepted",
  "note": "Verified tone and policy boundaries."
}
```

Valid decisions are `accepted`, `rejected`, and `needs_review`.

Candidate responses keep the original arrays and add an easier structured form:

```json
{
  "reason_codes": ["near_duplicate"],
  "explanations": ["Similarity to an accepted example is 0.94."],
  "quality_reasons": [
    {"code": "near_duplicate", "evidence": "Similarity to an accepted example is 0.94."}
  ]
}
```

`quality_reasons` pairs each stored code with its evidence in order. Existing clients may continue
using `reason_codes` and `explanations`; new clients should prefer the structured field and retain
unknown codes rather than discarding them.

## Exports

`POST /api/v1/runs/{run_id}/exports` creates an immutable snapshot from the effective accepted set.

```json
{
  "project_id": "project-id",
  "name": "Support fine-tuning v1",
  "formats": ["parquet"],
  "train_percent": 90,
  "validation_percent": 5,
  "test_percent": 5
}
```

`project_id` is optional for older API clients, but recommended. It lets the server reject a stale
or mismatched project/run selection before packaging any data.

Use `GET /api/v1/exports`, `GET /api/v1/exports/{export_id}`, and
`GET /api/v1/exports/{export_id}/download/{filename}` to inspect and retrieve artifacts.

## Errors

Errors use an RFC 7807-style response and include the request ID used in logs:

```json
{
  "type": "about:blank",
  "title": "Validation error",
  "status": 422,
  "detail": "One or more fields are invalid.",
  "code": "request_validation_failed",
  "instance": "/api/v1/runs",
  "request_id": "...",
  "errors": [{"loc": ["body", "provider"], "msg": "...", "type": "..."}]
}
```

Clients should branch on `code` and field-level `errors`; `title` and `detail` are intended for
people and may become more specific over time. Export dependency failures use these stable codes:

| Code | Field | Meaning |
|---|---|---|
| `export_project_not_found` | `body.project_id` | The selected project no longer exists. |
| `export_run_not_found` | `path.run_id` | The selected run no longer exists. |
| `export_run_project_mismatch` | `path.run_id` | The run does not belong to the selected project. |
| `export_run_not_complete` | `path.run_id` | The run is not in a completed state. |
| `export_run_has_no_accepted_examples` | `path.run_id` | No effective accepted examples can be packaged. |
