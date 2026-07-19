"""Public HTTP request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

from dataset_foundry.domain import (
    CandidateDecision,
    ExportFormat,
    ExportManifest,
    ProviderName,
    QualityComponent,
    TrainingExample,
)


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


T = TypeVar("T")


class Page(ApiModel, Generic[T]):
    items: list[T]
    next_cursor: str | None = None


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=4_000)


class ProjectView(ApiModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    seed_count: int = 0
    generated_count: int = 0
    accepted_count: int = 0
    last_activity: datetime
    active_run_id: str | None = None


class DatasetView(ApiModel):
    id: str
    project_id: str
    name: str
    source_format: str
    source_filename: str | None
    row_count: int
    duplicate_count: int = 0
    fingerprint: str
    created_at: datetime


class RecipeCreate(ApiModel):
    dataset_id: str | None = None
    name: str = Field(min_length=1, max_length=160)
    task_description: str = "Generate high-quality instruction-response training examples."
    target_count: int = Field(ge=1, le=10_000)
    batch_size: int = Field(default=10, ge=1, le=50)
    candidate_multiplier: int = Field(default=3, ge=1, le=20)
    min_quality_score: float = Field(default=0.72, ge=0, le=1)
    max_similarity: float = Field(default=0.92, ge=0, le=1)
    seed: int = Field(default=42, ge=0, le=2_147_483_647)
    language: str = Field(default="en", min_length=2, max_length=32)
    constraints: list[str] = Field(default_factory=list, max_length=50)
    diversity_axes: dict[str, list[str]] = Field(default_factory=dict)
    provider: ProviderName = ProviderName.offline
    model: str = "offline-deterministic-v1"
    allow_external_data_transfer: bool = False


class RecipeView(ApiModel):
    id: str
    project_id: str
    dataset_id: str
    name: str
    task_description: str
    target_count: int
    batch_size: int
    candidate_multiplier: int
    min_quality_score: float
    max_similarity: float
    seed: int
    language: str
    constraints: list[str]
    diversity_axes: dict[str, list[str]]
    provider: ProviderName
    model: str
    allow_external_data_transfer: bool
    created_at: datetime


class PreflightRequest(ApiModel):
    dataset_id: str | None = None
    provider: ProviderName | None = None
    model: str | None = Field(default=None, min_length=1, max_length=256)
    allow_external_data_transfer: bool | None = None


class PreflightView(ApiModel):
    ready: bool
    worker_ready: bool
    provider: ProviderName
    model: str
    seed_count: int
    target_count: int
    candidate_budget: int
    call_budget: int
    estimated_tokens: int
    external_data_transfer_required: bool
    blockers: list[str]


class SystemStatusView(ApiModel):
    api_ready: bool = True
    worker_ready: bool
    worker_state: Literal["idle", "busy", "stale", "stopped", "missing"]
    worker_id: str | None = None
    current_job_id: str | None = None
    heartbeat_at: datetime | None = None
    expires_at: datetime | None = None


class RunCreate(ApiModel):
    project_id: str | None = None
    dataset_id: str | None = None
    recipe_id: str
    provider: ProviderName | None = None
    model: str | None = Field(default=None, min_length=1, max_length=256)
    allow_external_data_transfer: bool | None = None


class RunView(ApiModel):
    id: str
    project_id: str
    project_name: str
    dataset_id: str
    recipe_id: str
    name: str
    provider: ProviderName
    model: str
    status: str
    target_count: int
    candidate_budget: int
    generated_count: int
    accepted_count: int
    rejected_count: int
    needs_review_count: int
    progress: float
    average_quality: float | None
    duplicate_rate: float
    error_type: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class QualityReasonView(ApiModel):
    code: str
    evidence: str | None = None


class CandidateView(ApiModel):
    id: str
    run_id: str
    example: TrainingExample
    automated_decision: CandidateDecision | None
    effective_decision: CandidateDecision | None
    quality_score: float | None
    reason_codes: list[str]
    quality_reasons: list[QualityReasonView]
    components: list[QualityComponent]
    explanations: list[str]
    nearest_match_id: str | None
    nearest_similarity: float | None
    reviewer_note: str | None
    source_seed_ids: list[str]
    source_examples: list[TrainingExample]
    generation_index: int
    provider: ProviderName
    model: str
    created_at: datetime


class ReviewCreate(ApiModel):
    decision: CandidateDecision
    note: str | None = Field(default=None, max_length=4_000)
    reviewer: str = Field(default="local-user", min_length=1, max_length=160)


class ReviewView(ApiModel):
    id: str
    candidate_id: str
    decision: CandidateDecision
    note: str | None
    reviewer: str
    created_at: datetime


class ExportCreate(ApiModel):
    project_id: str | None = Field(default=None, min_length=1, max_length=128)
    name: str = Field(default="Dataset export", min_length=1, max_length=120)
    formats: list[ExportFormat] = Field(
        default_factory=lambda: list(ExportFormat),
        min_length=1,
    )
    train_percent: int = Field(default=90, ge=0, le=100)
    validation_percent: int = Field(default=5, ge=0, le=100)
    test_percent: int = Field(default=5, ge=0, le=100)

    @model_validator(mode="after")
    def valid_export_selection(self) -> Self:
        if len(set(self.formats)) != len(self.formats):
            raise ValueError("export formats must be unique")
        if self.train_percent + self.validation_percent + self.test_percent != 100:
            raise ValueError("export split percentages must sum to 100")
        return self


class ArtifactView(ApiModel):
    filename: str
    format: ExportFormat | None
    split: str | None
    row_count: int | None
    size_bytes: int
    sha256: str
    download_url: str


class ExportView(ApiModel):
    id: str
    run_id: str
    status: str
    manifest: ExportManifest
    artifacts: list[ArtifactView]
    created_at: datetime


class ProviderStatus(ApiModel):
    id: ProviderName
    label: str
    configured: bool
    live: bool
    requires_external_data_transfer: bool
    model: str


class ProvidersView(ApiModel):
    default_provider: ProviderName
    providers: list[ProviderStatus]


class RunCounts(ApiModel):
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    cancelled: int = 0


class CandidateCounts(ApiModel):
    accepted: int = 0
    needs_review: int = 0
    rejected: int = 0


class OverviewView(ApiModel):
    projects: int
    datasets: int
    seed_examples: int
    generated_examples: int
    runs: RunCounts
    candidates: CandidateCounts
    exports: int


class AuditEventView(ApiModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    actor: str
    payload: dict[str, object]
    created_at: datetime
