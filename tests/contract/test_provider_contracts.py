from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from openai.lib._pydantic import to_strict_json_schema

from dataset_foundry.domain import (
    ChatMessage,
    GenerationBatchRequest,
    GenerationRecipe,
    MessageRole,
    ProviderName,
    TrainingExample,
)
from dataset_foundry.providers import (
    AnthropicProvider,
    OpenAIProvider,
    ProviderCandidate,
    ProviderCandidateBatch,
    ProviderIncompleteError,
    ProviderRefusalError,
    ProviderResponseError,
    ProviderTransientError,
)


class FakeParseEndpoint:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    async def parse(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RateLimitError(Exception):
    status_code = 429


def seed() -> TrainingExample:
    return TrainingExample(
        id="seed-a",
        messages=[
            ChatMessage(role=MessageRole.user, content="How can I update my billing email?"),
            ChatMessage(
                role=MessageRole.assistant,
                content="Open Billing settings and save the new notification address.",
            ),
        ],
    )


def parsed_batch(count: int = 2) -> ProviderCandidateBatch:
    return ProviderCandidateBatch(
        candidates=[
            ProviderCandidate(
                messages=[
                    ChatMessage(
                        role=MessageRole.user,
                        content=f"Billing scenario {index}: where is the email setting?",
                    ),
                    ChatMessage(
                        role=MessageRole.assistant,
                        content=f"Open Billing, edit Notifications, and verify address {index}.",
                    ),
                ],
                source_seed_ids=["seed-a"],
            )
            for index in range(count)
        ]
    )


def test_provider_schema_has_no_open_objects() -> None:
    """Every object in the OpenAI structured-output schema must be closed."""

    schema = to_strict_json_schema(ProviderCandidateBatch)

    def assert_closed(value: object) -> None:
        if isinstance(value, dict):
            if value.get("type") == "object":
                assert value.get("additionalProperties") is False
            for child in value.values():
                assert_closed(child)
        elif isinstance(value, list):
            for child in value:
                assert_closed(child)

    assert_closed(schema)


def request(provider: ProviderName) -> GenerationBatchRequest:
    return GenerationBatchRequest(
        run_id=f"run-{provider.value}",
        recipe=GenerationRecipe(
            name="live structured",
            target_count=2,
            batch_size=2,
            provider=provider,
            model="test-model",
            allow_external_data_transfer=True,
        ),
        seed_examples=[seed()],
        batch_index=0,
        requested_count=2,
    )


@pytest.mark.asyncio
async def test_openai_uses_responses_parse_and_normalizes_trace() -> None:
    endpoint = FakeParseEndpoint(
        [
            SimpleNamespace(
                id="response-1",
                status="completed",
                output_parsed=parsed_batch(),
                output=[],
                usage=SimpleNamespace(input_tokens=120, output_tokens=240),
            )
        ]
    )
    provider = OpenAIProvider(
        model="test-model",
        client=SimpleNamespace(responses=endpoint),
    )

    batch = await provider.generate_batch(request(ProviderName.openai))

    assert endpoint.calls[0]["text_format"] is ProviderCandidateBatch
    assert endpoint.calls[0]["model"] == "test-model"
    assert batch.candidates[0].provider_trace.request_id == "response-1"
    assert batch.candidates[0].provider_trace.input_tokens == 120
    assert batch.candidates[0].candidate_fingerprint is not None


@pytest.mark.asyncio
async def test_anthropic_uses_messages_parse_and_normalizes_trace() -> None:
    endpoint = FakeParseEndpoint(
        [
            SimpleNamespace(
                id="message-1",
                stop_reason="end_turn",
                parsed_output=parsed_batch(),
                usage=SimpleNamespace(input_tokens=100, output_tokens=220),
            )
        ]
    )
    provider = AnthropicProvider(
        model="test-model",
        client=SimpleNamespace(messages=endpoint),
    )

    batch = await provider.generate_batch(request(ProviderName.anthropic))

    assert endpoint.calls[0]["output_format"] is ProviderCandidateBatch
    assert endpoint.calls[0]["messages"][0]["role"] == "user"
    assert batch.candidates[0].provider_trace.request_id == "message-1"
    assert batch.candidates[0].provider_trace.output_tokens == 220


@pytest.mark.asyncio
async def test_openai_refusal_and_incomplete_are_terminal() -> None:
    refusal = SimpleNamespace(
        id="response-refusal",
        status="completed",
        output_parsed=None,
        output=[SimpleNamespace(content=[SimpleNamespace(type="refusal")])],
    )
    incomplete = SimpleNamespace(
        id="response-short",
        status="incomplete",
        output_parsed=None,
        output=[],
    )
    refusal_provider = OpenAIProvider(
        model="test-model",
        client=SimpleNamespace(responses=FakeParseEndpoint([refusal])),
    )
    incomplete_provider = OpenAIProvider(
        model="test-model",
        client=SimpleNamespace(responses=FakeParseEndpoint([incomplete])),
    )

    with pytest.raises(ProviderRefusalError):
        await refusal_provider.generate_batch(request(ProviderName.openai))
    with pytest.raises(ProviderIncompleteError):
        await incomplete_provider.generate_batch(request(ProviderName.openai))


@pytest.mark.asyncio
async def test_anthropic_refusal_and_incomplete_are_terminal() -> None:
    refusal_provider = AnthropicProvider(
        model="test-model",
        client=SimpleNamespace(
            messages=FakeParseEndpoint([SimpleNamespace(stop_reason="refusal", parsed_output=None)])
        ),
    )
    incomplete_provider = AnthropicProvider(
        model="test-model",
        client=SimpleNamespace(
            messages=FakeParseEndpoint(
                [SimpleNamespace(stop_reason="max_tokens", parsed_output=None)]
            )
        ),
    )

    with pytest.raises(ProviderRefusalError):
        await refusal_provider.generate_batch(request(ProviderName.anthropic))
    with pytest.raises(ProviderIncompleteError):
        await incomplete_provider.generate_batch(request(ProviderName.anthropic))


@pytest.mark.asyncio
async def test_transient_failure_retries_with_a_hard_cap() -> None:
    success = SimpleNamespace(
        id="response-retry",
        status="completed",
        output_parsed=parsed_batch(),
        output=[],
        usage=None,
    )
    endpoint = FakeParseEndpoint([RateLimitError(), success])
    sleeps: list[float] = []

    async def capture_sleep(delay: float) -> None:
        sleeps.append(delay)

    provider = OpenAIProvider(
        model="test-model",
        client=SimpleNamespace(responses=endpoint),
        max_retries=1,
        retry_base_seconds=0.01,
        sleep=capture_sleep,
    )

    result = await provider.generate_batch(request(ProviderName.openai))

    assert len(result.candidates) == 2
    assert len(endpoint.calls) == 2
    assert sleeps == [0.01]


@pytest.mark.asyncio
async def test_transient_failure_does_not_retry_forever() -> None:
    endpoint = FakeParseEndpoint([RateLimitError(), RateLimitError()])
    provider = AnthropicProvider(
        model="test-model",
        client=SimpleNamespace(messages=endpoint),
        max_retries=1,
        retry_base_seconds=0,
    )

    with pytest.raises(ProviderTransientError):
        await provider.generate_batch(request(ProviderName.anthropic))
    assert len(endpoint.calls) == 2


@pytest.mark.asyncio
async def test_provider_rejects_wrong_candidate_count() -> None:
    endpoint = FakeParseEndpoint(
        [
            SimpleNamespace(
                id="response-short",
                status="completed",
                output_parsed=parsed_batch(count=1),
                output=[],
                usage=None,
            )
        ]
    )
    provider = OpenAIProvider(
        model="test-model",
        client=SimpleNamespace(responses=endpoint),
    )

    with pytest.raises(ProviderResponseError):
        await provider.generate_batch(request(ProviderName.openai))
