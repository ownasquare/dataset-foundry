"""Canonical, provider-neutral domain contracts for Dataset Foundry."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator


def utc_now() -> datetime:
    """Return a timezone-aware timestamp suitable for persisted domain events."""

    return datetime.now(UTC)


class StrictModel(BaseModel):
    """Base contract that rejects accidental or provider-invented fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class MessageRole(StrEnum):
    system = "system"
    user = "user"
    assistant = "assistant"


class ProviderName(StrEnum):
    offline = "offline"
    openai = "openai"
    anthropic = "anthropic"


class CandidateDecision(StrEnum):
    accepted = "accepted"
    rejected = "rejected"
    needs_review = "needs_review"


class ExportFormat(StrEnum):
    canonical_jsonl = "canonical_jsonl"
    openai_chat_jsonl = "openai_chat_jsonl"
    alpaca_jsonl = "alpaca_jsonl"
    parquet = "parquet"


class ChatMessage(StrictModel):
    role: MessageRole
    content: str = Field(min_length=1, max_length=100_000)

    @field_validator("content")
    @classmethod
    def content_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message content must not be blank")
        return value.strip()


def _validate_message_sequence(messages: list[ChatMessage]) -> list[ChatMessage]:
    roles = [message.role for message in messages]
    valid_sequences = (
        [MessageRole.user, MessageRole.assistant],
        [MessageRole.system, MessageRole.user, MessageRole.assistant],
    )
    if roles not in valid_sequences:
        raise ValueError(
            "messages must be user/assistant or system/user/assistant in canonical order"
        )
    return messages


class TrainingExample(StrictModel):
    """One canonical chat-style fine-tuning example."""

    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=2, max_length=3)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    source_id: str | None = Field(default=None, max_length=256)
    root_seed_id: str | None = Field(default=None, max_length=256)

    @field_validator("messages")
    @classmethod
    def messages_are_canonical(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        return _validate_message_sequence(messages)

    @property
    def instruction(self) -> str:
        return next(
            message.content for message in self.messages if message.role is MessageRole.user
        )

    @property
    def response(self) -> str:
        return next(
            message.content for message in self.messages if message.role is MessageRole.assistant
        )

    @property
    def system_prompt(self) -> str | None:
        first = self.messages[0]
        return first.content if first.role is MessageRole.system else None


class GenerationRecipe(StrictModel):
    """Bounded generation settings captured with each run."""

    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=160)
    dataset_id: str | None = Field(default=None, max_length=128)
    task_description: str = Field(
        default="Generate high-quality instruction-response training examples.",
        min_length=1,
        max_length=4_000,
    )
    target_count: int = Field(ge=1, le=10_000)
    batch_size: int = Field(default=10, ge=1, le=50)
    candidate_multiplier: int = Field(default=3, ge=1, le=20)
    quality_threshold: float = Field(default=0.72, ge=0, le=1)
    similarity_threshold: float = Field(default=0.92, ge=0, le=1)
    provider: ProviderName = ProviderName.offline
    model: str = Field(default="offline-deterministic-v1", min_length=1, max_length=256)
    random_seed: int = Field(default=42, ge=0, le=2_147_483_647)
    language: str = Field(default="en", min_length=2, max_length=32)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    diversity_axes: dict[str, list[str]] = Field(default_factory=dict)
    max_concurrency: int = Field(default=2, ge=1, le=20)
    max_retries: int = Field(default=3, ge=0, le=10)
    allow_external_data_transfer: bool = False

    @field_validator("constraints")
    @classmethod
    def constraints_are_bounded(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("constraints must not contain blank values")
        return cleaned

    @field_validator("diversity_axes")
    @classmethod
    def diversity_axes_are_usable(cls, values: dict[str, list[str]]) -> dict[str, list[str]]:
        if len(values) > 20:
            raise ValueError("at most 20 diversity axes are allowed")
        for name, options in values.items():
            if not name.strip() or not options or len(options) > 100:
                raise ValueError("each diversity axis requires a name and 1..100 options")
            if any(not option.strip() for option in options):
                raise ValueError("diversity axis options must not be blank")
        return values

    @model_validator(mode="after")
    def live_providers_require_consent(self) -> Self:
        if self.provider is not ProviderName.offline and not self.allow_external_data_transfer:
            raise ValueError("live providers require allow_external_data_transfer=true")
        return self

    @property
    def candidate_budget(self) -> int:
        return self.target_count * self.candidate_multiplier


class ProviderTrace(StrictModel):
    provider: ProviderName
    model: str = Field(min_length=1, max_length=256)
    mode: str = Field(default="structured", min_length=1, max_length=64)
    request_id: str | None = Field(default=None, max_length=256)
    prompt_version: str = Field(default="v1", min_length=1, max_length=64)
    latency_ms: float | None = Field(default=None, ge=0)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class GeneratedCandidate(StrictModel):
    """A schema-valid candidate before automated quality disposition."""

    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=128)
    messages: list[ChatMessage] = Field(min_length=2, max_length=3)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    source_seed_ids: list[str] = Field(default_factory=list, max_length=50)
    generation_index: int = Field(default=0, ge=0)
    provider_trace: ProviderTrace
    candidate_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)

    @field_validator("messages")
    @classmethod
    def messages_are_canonical(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        return _validate_message_sequence(messages)

    @field_validator("source_seed_ids")
    @classmethod
    def seed_ids_are_unique(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values]
        if any(not value for value in cleaned):
            raise ValueError("source seed IDs must not be blank")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("source seed IDs must be unique")
        return cleaned

    def as_training_example(self) -> TrainingExample:
        return TrainingExample(
            id=self.id,
            messages=self.messages,
            metadata=self.metadata,
            source_id=self.id,
            root_seed_id=self.source_seed_ids[0] if self.source_seed_ids else None,
        )


class GenerationBatchRequest(StrictModel):
    run_id: str = Field(min_length=1, max_length=128)
    recipe: GenerationRecipe
    seed_examples: list[TrainingExample] = Field(min_length=1, max_length=100)
    batch_index: int = Field(ge=0)
    requested_count: int = Field(ge=1, le=50)

    @model_validator(mode="after")
    def requested_count_respects_recipe(self) -> Self:
        if self.requested_count > self.recipe.batch_size:
            raise ValueError("requested_count must not exceed recipe batch_size")
        return self


class CandidateBatch(StrictModel):
    candidates: list[GeneratedCandidate] = Field(min_length=1, max_length=50)


class QualityComponent(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    score: float = Field(ge=0, le=1)
    passed: bool
    reason_code: str | None = Field(default=None, max_length=80)
    explanation: str = Field(min_length=1, max_length=1_000)


class QualityReport(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=128)
    score: float = Field(ge=0, le=1)
    automated_decision: CandidateDecision
    final_decision: CandidateDecision | None = None
    components: list[QualityComponent] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    explanations: list[str] = Field(default_factory=list)
    nearest_match_id: str | None = Field(default=None, max_length=128)
    nearest_similarity: float | None = Field(default=None, ge=-1, le=1)
    embedder_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    created_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def rejected_reports_explain_the_rejection(self) -> Self:
        if self.automated_decision is CandidateDecision.rejected and not self.reason_codes:
            raise ValueError("rejected quality reports require at least one reason code")
        return self

    @property
    def decision(self) -> CandidateDecision:
        return self.final_decision or self.automated_decision


class ReviewDecision(StrictModel):
    candidate_id: str = Field(min_length=1, max_length=128)
    decision: CandidateDecision
    note: str | None = Field(default=None, max_length=4_000)
    reviewer: str = Field(default="local-user", min_length=1, max_length=160)
    created_at: datetime = Field(default_factory=utc_now)


class RunSummary(StrictModel):
    id: str = Field(min_length=1, max_length=128)
    dataset_id: str = Field(min_length=1, max_length=128)
    recipe_id: str = Field(min_length=1, max_length=128)
    status: str = Field(min_length=1, max_length=32)
    target_count: int = Field(ge=1, le=10_000)
    candidate_budget: int = Field(ge=1, le=200_000)
    generated_count: int = Field(default=0, ge=0)
    accepted_count: int = Field(default=0, ge=0)
    rejected_count: int = Field(default=0, ge=0)
    needs_review_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def counts_reconcile(self) -> Self:
        classified = self.accepted_count + self.rejected_count + self.needs_review_count
        if classified > self.generated_count:
            raise ValueError("classified candidate counts cannot exceed generated_count")
        if self.generated_count > self.candidate_budget:
            raise ValueError("generated_count cannot exceed candidate_budget")
        return self


class ExportArtifact(StrictModel):
    path: str = Field(min_length=1, max_length=1_024)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int = Field(ge=0)
    row_count: int | None = Field(default=None, ge=0)
    format: ExportFormat | None = None
    split: str | None = Field(default=None, max_length=32)


class ExportManifest(StrictModel):
    schema_version: str = Field(default="1.0", min_length=1, max_length=32)
    export_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    name: str = Field(default="Dataset export", min_length=1, max_length=120)
    created_at: datetime = Field(default_factory=utc_now)
    total_count: int = Field(ge=0)
    split_counts: dict[str, int]
    split_ratios: dict[str, float]
    requested_split_ratios: dict[str, float] = Field(
        default_factory=lambda: {"train": 0.9, "validation": 0.05, "test": 0.05}
    )
    recipe_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    dataset_fingerprint: str | None = Field(default=None, min_length=64, max_length=64)
    provider: str | None = Field(default=None, max_length=64)
    model: str | None = Field(default=None, max_length=256)
    quality_threshold: float = Field(ge=0, le=1)
    similarity_threshold: float = Field(ge=0, le=1)
    requested_formats: list[ExportFormat] = Field(default_factory=list)
    artifacts: list[ExportArtifact]

    @model_validator(mode="after")
    def split_counts_match_total(self) -> Self:
        if sum(self.split_counts.values()) != self.total_count:
            raise ValueError("split counts must sum to total_count")
        return self
