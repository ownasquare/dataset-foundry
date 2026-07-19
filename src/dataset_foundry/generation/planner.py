"""Bounded generation planning and privacy/cost preflight."""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict, Field

from dataset_foundry.domain import GenerationRecipe, ProviderName, TrainingExample


class GenerationPreflight(BaseModel):
    """A serializable upper-bound estimate produced before a run is queued."""

    model_config = ConfigDict(extra="forbid")

    ready: bool
    provider: ProviderName
    model: str
    target_count: int = Field(ge=1)
    candidate_budget: int = Field(ge=1)
    call_budget: int = Field(ge=1)
    estimated_tokens: int = Field(ge=0)
    external_data_transfer_required: bool
    blockers: list[str] = Field(default_factory=list)


def build_preflight(
    recipe: GenerationRecipe,
    seed_examples: list[TrainingExample],
    *,
    provider_configured: bool = True,
) -> GenerationPreflight:
    """Compute hard generation bounds without calling a provider."""

    blockers: list[str] = []
    if not seed_examples:
        blockers.append("At least one valid seed example is required.")
    live = recipe.provider is not ProviderName.offline
    if live and not recipe.allow_external_data_transfer:
        blockers.append("Live providers require explicit external data transfer consent.")
    if not provider_configured:
        blockers.append(f"The {recipe.provider.value} provider is not configured.")

    call_budget = math.ceil(recipe.candidate_budget / recipe.batch_size)
    seed_characters = sum(
        len(message.content) for seed in seed_examples for message in seed.messages
    )
    prompt_tokens_per_call = max(256, math.ceil(seed_characters / 4) + 300)
    output_tokens_per_candidate = 320
    estimated_tokens = (
        prompt_tokens_per_call * call_budget + output_tokens_per_candidate * recipe.candidate_budget
    )
    return GenerationPreflight(
        ready=not blockers,
        provider=recipe.provider,
        model=recipe.model,
        target_count=recipe.target_count,
        candidate_budget=recipe.candidate_budget,
        call_budget=call_budget,
        estimated_tokens=estimated_tokens,
        external_data_transfer_required=live,
        blockers=blockers,
    )
