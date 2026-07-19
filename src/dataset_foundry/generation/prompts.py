"""Versioned, reproducible prompts for native structured-output providers."""

from __future__ import annotations

import json

from dataset_foundry.domain import GenerationBatchRequest

PROMPT_VERSION = "structured-generation-v1"


def build_generation_prompt(request: GenerationBatchRequest) -> tuple[str, str]:
    """Return a provider-neutral system instruction and JSON-backed user prompt."""

    recipe = request.recipe
    system = (
        "You create synthetic fine-tuning examples. Return only the requested structured "
        "output. Every candidate must use either user/assistant or "
        "system/user/assistant message order. Preserve factual intent while creating useful, "
        "meaningfully diverse examples. Do not include secrets, unsupported claims, or fields "
        "outside the schema. Include source_seed_ids for every candidate; metadata and runtime "
        "provenance are added by the server."
    )
    payload = {
        "run_id": request.run_id,
        "batch_index": request.batch_index,
        "requested_count": request.requested_count,
        "task_description": recipe.task_description,
        "language": recipe.language,
        "constraints": recipe.constraints,
        "diversity_axes": recipe.diversity_axes,
        "provider": recipe.provider.value,
        "model": recipe.model,
        "prompt_version": PROMPT_VERSION,
        "seed_examples": [
            {
                "id": seed.id,
                "messages": [message.model_dump(mode="json") for message in seed.messages],
                "metadata": seed.metadata,
            }
            for seed in request.seed_examples
        ],
    }
    user = (
        f"Generate exactly {request.requested_count} candidates from this generation request. "
        "Each candidate must cite one or more supplied seed IDs in source_seed_ids. Vary "
        "scenario, phrasing, difficulty, context, and response structure without producing "
        "near-duplicates.\n\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return system, user
