# Troubleshooting

## The UI loads but shows a connection error

Check `http://127.0.0.1:8765/health`, then run `uv run dataset-foundry doctor`. During Vite
development, confirm the API is on the configured proxy port. A static frontend build does not run
the API or worker by itself.

## A run remains queued

Start `uv run dataset-foundry worker`. If a worker exited, wait for its lease to expire; the next
worker will recover the job. Inspect run events rather than editing SQLite state manually.

## A live provider is blocked

Provider status distinguishes configuration from authorization. Confirm the server process has the
matching key, the recipe uses a current model ID, and the run explicitly approves external data
transfer. Do not put keys in the request or browser settings.

## The target count was not reached

Inspect candidate-budget exhaustion, rejection reason distribution, quality threshold, similarity
threshold, and provider attempts. Create a new recipe with a justified change; do not rewrite the
completed run's thresholds.

## Too many near duplicates

Add representative seed strata and useful diversity axes before merely raising the similarity
threshold. Open candidate Details to see nearest-match IDs and scores. Confirm all compared vectors
share the same embedder fingerprint.

## An export has fewer rows than expected

Exports include the effective accepted set at snapshot time. Review overrides after an export do not
mutate it; create a new export. The manifest records total and actual split counts.

## Parquet cannot be opened

Verify the manifest hash first, then load with a PyArrow/Hugging Face version compatible with the
project lock. An incomplete staging directory is not a completed export and should not be consumed.

## Port 8765 is already in use

Stop the previous Dataset Foundry process or choose another loopback port through settings. Update
the Vite proxy when using a non-default development port.

