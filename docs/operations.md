# Operations

## Processes

The normal local installation runs two Python processes:

- `dataset-foundry serve` owns HTTP and the built React application.
- `dataset-foundry worker` claims and processes queued jobs.

Running the worker separately keeps generation outside the request lifecycle. One worker is the
recommended SQLite posture. The worker can also run once for scripting and deterministic tests.

## Data paths

Defaults are relative to the repository:

- database: `.data/dataset-foundry.db`
- artifacts: `.data/artifacts/`

Both are ignored by Git. Back up the SQLite database and complete artifact directories together if
historical run-to-export evidence must be preserved.

## Health

- `/health` proves the API process is accepting requests.
- `/ready` verifies application initialization and database access.
- `/metrics` exposes bounded operational counts; it is not a full telemetry backend.
- `/api/v1/system/status` combines API readiness with persisted worker-heartbeat state. The worker
  is ready only while an `idle` or `busy` heartbeat remains current.
- `dataset-foundry doctor` checks settings, storage, database, frontend assets, and provider
  readiness without exposing secrets.

If the workbench reports **API ready · worker offline**, start `uv run dataset-foundry worker` in a
second terminal. With containers, use `docker compose up --build --wait`; the worker is part of that
stack.

## Recovery

A worker lease includes an expiration and heartbeat, while a separate persisted presence heartbeat
lets the API distinguish `idle`, `busy`, `stale`, `stopped`, and `missing` workers. If a worker exits
mid-batch, another worker may claim the job after lease expiry. Candidate uniqueness makes replay idempotent. Operators should
inspect the run event log and candidate counts before retrying a failed provider run; terminal runs
remain immutable, so changed settings use a new run.

## Containers

```bash
make quickstart
```

The quickstart runs `docker compose up --build --wait`. A one-shot bootstrap service idempotently
prepares the offline sample before the API starts; the API and worker then share the same named data
volume. Compose publishes only `127.0.0.1:8765`, runs as non-root, drops capabilities, and keeps the
root filesystem read-only. It does not inject live-provider keys by default.

When an operator explicitly sets `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the repository `.env`,
Compose passes it to both the API and worker. Blank or absent keys remain unconfigured, and the
bootstrap service still uses the offline provider.

Use `make stop` to keep the volume. `make reset-demo` removes the volume and therefore deletes the
container-backed database and artifacts.

## Scaling

Use the deterministic CI benchmark for a quick gate:

```bash
make benchmark-ci
```

That command measures the vectorized quality/export kernel. The durable benchmark exercises the
actual SQLite queue, worker, persisted quality reports, and immutable export path:

```bash
make benchmark-durable
```

Use `uv run python scripts/benchmark_scale.py --count 2000` for the 2,000-candidate kernel proof
and `uv run python scripts/benchmark_durable.py --count 2000` for the complete local product path.
Scale numbers are environment-specific and should include the mode and host details when published.

SQLite and the bundled worker are intentionally local-first. For multi-host execution, move job
leases and metadata to a production database/queue, keep the API contract stable, place artifacts in
object storage, and re-run recovery and idempotency tests against that infrastructure.

## Release checklist

1. Run `make check` with no provider keys.
2. Run `make benchmark-ci` and `make benchmark-durable`.
3. Validate `docker compose config --quiet` and build the locked image.
4. Run Playwright against the complete local workflow.
5. Record offline, mocked-provider, live-provider, browser, and hosted proof separately.
6. Build the wheel and install it into an isolated environment.
7. Verify the final manifest hashes by reloading each export format.
