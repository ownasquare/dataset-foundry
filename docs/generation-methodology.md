# Generation methodology

Dataset Foundry treats synthetic generation as a bounded data-production job, not a single prompt.
The objective is to reach a target number of accepted examples while preserving enough evidence to
explain what was requested, generated, filtered, reviewed, and exported.

## Recipe and preflight

A recipe captures:

- task description, language, constraints, and diversity axes;
- target accepted count and provider batch size;
- candidate multiplier, which caps total generated candidates;
- quality and near-duplicate thresholds;
- provider, model, concurrency, retry limit, and random seed; and
- whether external provider transfer is authorized.

Preflight returns the maximum candidate budget, maximum calls, a conservative token estimate, and
blocking conditions. A paid provider never falls back silently to offline mode: that would make
lineage and cost evidence false.

## Seed selection

The worker samples across the seed set rather than repeatedly expanding the first rows. Each
candidate records its source seed IDs. In offline mode, the stable random seed also chooses template
family, tone, difficulty, locale, and configured diversity axes. The same seeds and recipe therefore
produce the same offline candidate sequence.

Live model output is not claimed to be byte-reproducible. Dataset Foundry instead preserves the
recipe, provider/model ID, prompt version, source fingerprints, request trace when available, token
usage when available, and candidate fingerprints.

## Structured output

All providers implement one `generate_batch` contract and return a root `CandidateBatch` object.
OpenAI uses the Responses API Pydantic parser. Anthropic uses the Messages API Pydantic structured
output helper. The shared schema requires every field and rejects additional properties.

Provider schema acceptance is only the first gate. Dataset Foundry revalidates business rules such
as message order, non-blank content, batch bounds, source lineage, and recipe constraints.

Refusals, truncation, timeouts, and invalid outputs are attempt evidence. Only transient timeout,
rate-limit, and server failures are eligible for bounded retry. A refusal or exhausted output limit
is not disguised as a successful empty batch.

## Provider modes

### Offline deterministic

Offline mode is the default for onboarding, CI, scale checks, and demos. It makes no network calls,
uses versioned transformation families, and clearly labels provider provenance as deterministic.
It proves pipeline behavior and scale, not frontier-model response quality.

### OpenAI

The OpenAI adapter keeps the model configurable and uses native structured outputs. The default
example model is selected for current high-volume generation, but the run persists the exact model
ID so later model changes cannot rewrite history.

### Anthropic

The Anthropic adapter also keeps the model configurable and uses native structured outputs. It does
not send non-default sampling parameters to models that reject them; diversity comes from seed
selection, explicit axes, and prompt constraints.

## Stop conditions

A run stops when one of these becomes true:

- the accepted target is reached;
- the candidate budget is exhausted;
- cancellation is observed;
- a non-retryable provider or validation error fails the run; or
- bounded retries are exhausted.

Candidate-budget exhaustion is a truthful terminal result. The run retains generated, accepted,
needs-review, and rejected counts so a user can adjust thresholds or the recipe in a new run.

