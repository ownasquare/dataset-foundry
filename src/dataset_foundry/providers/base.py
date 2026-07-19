"""Provider-neutral generation protocol and failure taxonomy."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataset_foundry.domain import (
    CandidateBatch,
    ChatMessage,
    GeneratedCandidate,
    GenerationBatchRequest,
    ProviderName,
    ProviderTrace,
)


class ProviderCandidate(BaseModel):
    """Only semantic fields a model is allowed to author."""

    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=2, max_length=3)
    source_seed_ids: list[str] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def messages_are_canonical(self) -> ProviderCandidate:
        roles = [message.role.value for message in self.messages]
        if roles not in (["user", "assistant"], ["system", "user", "assistant"]):
            raise ValueError("provider messages must use canonical chat order")
        return self


class ProviderCandidateBatch(BaseModel):
    """Strict native structured-output schema with server-owned provenance omitted."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[ProviderCandidate] = Field(min_length=1, max_length=50)


class ProviderError(RuntimeError):
    """Base class for a classified provider failure."""


class ProviderConfigurationError(ProviderError):
    """The provider cannot run with the supplied local configuration."""


class ProviderPrivacyError(ProviderError):
    """External transfer was requested without explicit user consent."""


class ProviderTransientError(ProviderError):
    """A retryable network, rate-limit, or provider server failure."""


class ProviderRefusalError(ProviderError):
    """The provider explicitly refused the requested generation."""


class ProviderIncompleteError(ProviderError):
    """The provider stopped before returning a complete structured batch."""


class ProviderResponseError(ProviderError):
    """The provider response was absent, malformed, or violated the batch contract."""


class GenerationProvider(Protocol):
    """One structured-output provider implementation."""

    @property
    def name(self) -> ProviderName:
        """Stable provider identifier."""

    @property
    def model(self) -> str:
        """Configured provider model identifier."""

    async def generate_batch(self, request: GenerationBatchRequest) -> CandidateBatch:
        """Generate exactly ``request.requested_count`` schema-valid candidates."""


T = TypeVar("T")


async def retry_transient(
    operation: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    base_delay_seconds: float,
    is_transient: Callable[[Exception], bool],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Retry only explicitly classified transient failures with a fixed bound."""

    attempt = 0
    while True:
        try:
            return await operation()
        except Exception as exc:
            if not is_transient(exc):
                raise
            if attempt >= max_retries:
                raise ProviderTransientError(
                    f"provider transient failure after {attempt + 1} attempts"
                ) from exc
            delay = base_delay_seconds * (2**attempt)
            attempt += 1
            if delay:
                await sleep(delay)


def require_external_transfer_consent(request: GenerationBatchRequest) -> None:
    """Fail closed before any live-provider SDK receives seed data."""

    if (
        request.recipe.provider is not ProviderName.offline
        and not request.recipe.allow_external_data_transfer
    ):
        raise ProviderPrivacyError("live generation requires allow_external_data_transfer=true")


def validate_batch_size(batch: CandidateBatch, request: GenerationBatchRequest) -> None:
    """Reject under- or over-produced batches instead of silently padding them."""

    actual = len(batch.candidates)
    expected = request.requested_count
    if actual != expected:
        raise ProviderResponseError(
            f"provider returned {actual} candidates; exactly {expected} were requested"
        )


def fingerprint_messages(messages: list[ChatMessage]) -> str:
    """Return the canonical candidate fingerprint shared by all providers."""

    payload = [message.model_dump(mode="json") for message in messages]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def normalize_live_batch(
    batch: ProviderCandidateBatch,
    request: GenerationBatchRequest,
    *,
    provider: ProviderName,
    model: str,
    prompt_version: str,
    request_id: str | None,
    latency_ms: float,
    input_tokens: int | None,
    output_tokens: int | None,
) -> CandidateBatch:
    """Enforce lineage and provenance instead of trusting provider-authored traces."""

    actual = len(batch.candidates)
    if actual != request.requested_count:
        raise ProviderResponseError(
            f"provider returned {actual} candidates; exactly "
            f"{request.requested_count} were requested"
        )
    allowed_seed_ids = {seed.id for seed in request.seed_examples}
    normalized: list[GeneratedCandidate] = []
    for offset, candidate in enumerate(batch.candidates):
        source_seed_ids = candidate.source_seed_ids
        if not set(source_seed_ids).issubset(allowed_seed_ids):
            raise ProviderResponseError("provider returned an unknown source seed ID")
        fingerprint = fingerprint_messages(candidate.messages)
        generation_index = request.batch_index * request.recipe.batch_size + offset
        candidate_id = hashlib.sha256(
            f"{request.run_id}:{fingerprint}:{generation_index}".encode()
        ).hexdigest()[:32]
        normalized.append(
            GeneratedCandidate(
                id=candidate_id,
                messages=candidate.messages,
                metadata={},
                source_seed_ids=source_seed_ids,
                generation_index=generation_index,
                provider_trace=ProviderTrace(
                    provider=provider,
                    model=model,
                    mode="structured",
                    request_id=request_id,
                    prompt_version=prompt_version,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                ),
                candidate_fingerprint=fingerprint,
            )
        )
    return CandidateBatch(candidates=normalized)
