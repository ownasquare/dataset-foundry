from __future__ import annotations

import pytest

from dataset_foundry.domain import (
    ChatMessage,
    GenerationBatchRequest,
    GenerationRecipe,
    MessageRole,
    ProviderName,
    TrainingExample,
)
from dataset_foundry.providers import OfflineProvider, ProviderConfigurationError


def seed_example(seed_id: str = "seed-1") -> TrainingExample:
    return TrainingExample(
        id=seed_id,
        messages=[
            ChatMessage(role=MessageRole.user, content="How do I reset my password?"),
            ChatMessage(
                role=MessageRole.assistant,
                content="Open account settings, choose Security, and request a reset link.",
            ),
        ],
        metadata={"topic": "account"},
    )


def offline_request(*, batch_index: int = 0, count: int = 4) -> GenerationBatchRequest:
    return GenerationBatchRequest(
        run_id="run-1",
        recipe=GenerationRecipe(
            name="support",
            target_count=12,
            batch_size=4,
            candidate_multiplier=2,
            random_seed=88,
            diversity_axes={"urgency": ["low", "high"]},
        ),
        seed_examples=[seed_example()],
        batch_index=batch_index,
        requested_count=count,
    )


@pytest.mark.asyncio
async def test_offline_provider_is_deterministic_and_returns_exact_batch() -> None:
    provider = OfflineProvider()
    request = offline_request()

    first = await provider.generate_batch(request)
    second = await provider.generate_batch(request)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert len(first.candidates) == request.requested_count
    assert len({candidate.candidate_fingerprint for candidate in first.candidates}) == 4
    assert all(candidate.source_seed_ids == ["seed-1"] for candidate in first.candidates)
    assert all(
        candidate.provider_trace.mode == "offline-deterministic" for candidate in first.candidates
    )


@pytest.mark.asyncio
async def test_offline_provider_changes_stratum_between_batches() -> None:
    provider = OfflineProvider()

    first = await provider.generate_batch(offline_request(batch_index=0))
    second = await provider.generate_batch(offline_request(batch_index=1))

    assert {candidate.candidate_fingerprint for candidate in first.candidates}.isdisjoint(
        {candidate.candidate_fingerprint for candidate in second.candidates}
    )
    assert [candidate.generation_index for candidate in second.candidates] == [4, 5, 6, 7]


@pytest.mark.asyncio
async def test_offline_provider_rejects_live_recipe() -> None:
    recipe = GenerationRecipe(
        name="live",
        target_count=2,
        batch_size=2,
        provider=ProviderName.openai,
        model="test-model",
        allow_external_data_transfer=True,
    )
    request = GenerationBatchRequest(
        run_id="run-live",
        recipe=recipe,
        seed_examples=[seed_example()],
        batch_index=0,
        requested_count=2,
    )

    with pytest.raises(ProviderConfigurationError):
        await OfflineProvider().generate_batch(request)
