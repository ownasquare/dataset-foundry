# Quality methodology

Quality filtering is explainable and reviewable. Dataset Foundry never collapses an unavailable
metric to zero and never deletes rejected candidates merely to make acceptance metrics look better.

## Gate order

```text
Pydantic and message-order validation
→ normalized exact-duplicate check
→ vector nearest-match check
→ component scoring
→ accepted / needs review / rejected
→ optional human override
```

Structural validity and exact duplication are hard gates. Remaining components contribute to a
bounded aggregate score. Each component stores its score, pass/fail result, reason code when
applicable, and a human-readable explanation.

## Components

- **Completeness:** required user and assistant content exists after normalization.
- **Useful length:** the response is substantial enough for the configured task without becoming
  uncontrolled boilerplate.
- **Instruction relevance:** the response shares meaningful task concepts with its instruction.
- **Lexical richness:** the example avoids pathological token repetition.
- **Boilerplate hygiene:** common generic filler and repeated disclaimers are penalized.
- **Seed novelty:** the candidate is not a copy of a source seed.
- **Accepted-pool diversity:** the candidate remains sufficiently distinct from examples already
  accepted in the same run.
- **Constraint adherence:** configured language and recipe constraints are checked when a
  deterministic check is available.

The run persists the threshold and component evidence, so changing defaults later does not change
the historical decision.

## Similarity

The key-free embedder hashes normalized token unigrams and bigrams into a fixed-width vector and
L2-normalizes it. Cosine similarity then identifies the nearest seed or accepted candidate. This is
an actual vector-similarity check, but it is labeled lexical rather than semantic.

Every embedder carries a fingerprint containing its algorithm, version, dimensions, and relevant
normalization settings. Vectors with different fingerprints are never compared. Optional semantic
or remote embedding adapters must implement the same protocol and preserve their model fingerprint.

An exact normalized match always rejects. A near match rejects when similarity is greater than or
equal to the recipe's configured threshold. The report retains nearest-match ID and similarity.

## Automated and human decisions

Automated decisions are:

- `accepted`: all hard gates passed and aggregate quality meets the recipe threshold;
- `needs_review`: structurally valid but close enough to a threshold or policy boundary to benefit
  from a human decision; or
- `rejected`: a hard gate failed or aggregate quality is below the reject boundary.

A reviewer may accept, reject, or return a candidate to needs-review with a note. The review becomes
the effective decision, while the original automated decision and evidence remain unchanged.

## Split leakage prevention

Export groups examples by root seed lineage before assigning train, validation, and test splits.
Related synthetic families therefore do not cross splits merely because their row IDs differ. The
manifest records actual split counts and ratios; small datasets are not described as exactly 90/5/5
when indivisible groups make that impossible.

