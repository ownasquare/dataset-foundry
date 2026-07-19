from __future__ import annotations

import pytest
from pydantic import ValidationError

from dataset_foundry.domain import (
    CandidateBatch,
    CandidateDecision,
    ChatMessage,
    GeneratedCandidate,
    GenerationBatchRequest,
    GenerationRecipe,
    MessageRole,
    ProviderName,
    ProviderTrace,
    QualityReport,
    TrainingExample,
)


def message(role: MessageRole, content: str) -> ChatMessage:
    return ChatMessage(role=role, content=content)


def example() -> TrainingExample:
    return TrainingExample(
        id="seed-1",
        messages=[
            message(MessageRole.user, "Explain how to update a delivery address."),
            message(MessageRole.assistant, "Verify the order, then update it before fulfillment."),
        ],
    )


def test_training_example_requires_user_then_assistant() -> None:
    with pytest.raises(ValidationError):
        TrainingExample(messages=[message(MessageRole.assistant, "orphan")])


def test_training_example_accepts_optional_system_message() -> None:
    training_example = TrainingExample(
        messages=[
            message(MessageRole.system, "Be concise."),
            message(MessageRole.user, "How do I cancel?"),
            message(MessageRole.assistant, "Open billing settings and select Cancel renewal."),
        ]
    )

    assert training_example.system_prompt == "Be concise."
    assert training_example.instruction == "How do I cancel?"
    assert training_example.response.startswith("Open billing")


def test_models_reject_extra_fields_and_blank_content() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="  ")
    with pytest.raises(ValidationError, match="Extra inputs"):
        ChatMessage(role="user", content="hello", invented=True)  # type: ignore[call-arg]


def test_recipe_rejects_unbounded_candidate_budget() -> None:
    with pytest.raises(ValidationError):
        GenerationRecipe(name="unsafe", target_count=100, candidate_multiplier=21)


def test_live_recipe_requires_explicit_external_transfer_consent() -> None:
    with pytest.raises(ValidationError, match="external_data_transfer"):
        GenerationRecipe(name="live", target_count=10, provider=ProviderName.openai)

    recipe = GenerationRecipe(
        name="live",
        target_count=10,
        provider=ProviderName.openai,
        model="configured-model",
        allow_external_data_transfer=True,
    )
    assert recipe.candidate_budget == 30


def test_generation_batch_request_respects_recipe_batch_size() -> None:
    recipe = GenerationRecipe(name="bounded", target_count=100, batch_size=4)
    with pytest.raises(ValidationError, match="batch_size"):
        GenerationBatchRequest(
            run_id="run-1",
            recipe=recipe,
            seed_examples=[example()],
            batch_index=0,
            requested_count=5,
        )


def test_candidate_batch_and_quality_report_are_provider_neutral() -> None:
    candidate = GeneratedCandidate(
        id="candidate-1",
        messages=example().messages,
        source_seed_ids=["seed-1"],
        provider_trace=ProviderTrace(
            provider=ProviderName.offline,
            model="offline-deterministic-v1",
            mode="offline-deterministic",
        ),
    )
    assert CandidateBatch(candidates=[candidate]).candidates == [candidate]

    with pytest.raises(ValidationError, match="reason code"):
        QualityReport(
            candidate_id=candidate.id,
            score=0.1,
            automated_decision=CandidateDecision.rejected,
        )
