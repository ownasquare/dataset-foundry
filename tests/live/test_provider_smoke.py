from __future__ import annotations

import os

import pytest

from dataset_foundry.config import Settings
from dataset_foundry.domain import (
    ChatMessage,
    GenerationBatchRequest,
    GenerationRecipe,
    ProviderName,
    TrainingExample,
)
from dataset_foundry.ingestion import fingerprint_dataset
from dataset_foundry.providers import ProviderRegistry


def approved_seed() -> TrainingExample:
    return TrainingExample(
        id="public-live-smoke-seed-v1",
        messages=[
            ChatMessage(
                role="user",
                content="How can a customer download a copy of a completed invoice?",
            ),
            ChatMessage(
                role="assistant",
                content="Open Billing history, choose the completed invoice, and select Download.",
            ),
        ],
        metadata={"classification": "public synthetic fixture"},
    )


@pytest.mark.live
@pytest.mark.asyncio
async def test_opt_in_live_structured_provider_smoke() -> None:
    """Make exactly one paid call only after explicit provider and seed-hash approval."""

    if os.getenv("DATASET_FOUNDRY_RUN_LIVE_TESTS") != "1":
        pytest.skip("set DATASET_FOUNDRY_RUN_LIVE_TESTS=1 to opt into one paid call")
    provider_value = os.getenv("DATASET_FOUNDRY_LIVE_PROVIDER")
    if provider_value not in {ProviderName.openai.value, ProviderName.anthropic.value}:
        pytest.fail("DATASET_FOUNDRY_LIVE_PROVIDER must be openai or anthropic")
    seed = approved_seed()
    expected_hash = fingerprint_dataset([seed])
    if os.getenv("DATASET_FOUNDRY_LIVE_SEED_SHA256") != expected_hash:
        pytest.fail(
            "DATASET_FOUNDRY_LIVE_SEED_SHA256 must match the approved public fixture: "
            f"{expected_hash}"
        )

    settings = Settings()
    provider_name = ProviderName(provider_value)
    if not settings.provider_configured(provider_value):
        pytest.fail(f"{provider_value} credential is not configured")
    model = (
        settings.openai_model if provider_name is ProviderName.openai else settings.anthropic_model
    )
    recipe = GenerationRecipe(
        name="one-call live structured smoke",
        target_count=1,
        batch_size=1,
        candidate_multiplier=1,
        max_retries=0,
        provider=provider_name,
        model=model,
        allow_external_data_transfer=True,
    )
    provider = ProviderRegistry(settings).get(provider_name, model)

    batch = await provider.generate_batch(
        GenerationBatchRequest(
            run_id="live-smoke",
            recipe=recipe,
            seed_examples=[seed],
            batch_index=0,
            requested_count=1,
        )
    )

    assert len(batch.candidates) == 1
    assert batch.candidates[0].provider_trace.provider is provider_name
    assert batch.candidates[0].source_seed_ids == [seed.id]
