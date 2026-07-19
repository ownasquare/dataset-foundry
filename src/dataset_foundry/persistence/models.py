"""SQLAlchemy persistence schema for local transactional truth."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from dataset_foundry.domain.models import utc_now
from dataset_foundry.domain.states import RunStatus


def new_id() -> str:
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    datasets: Mapped[list[DatasetRecord]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class DatasetRecord(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("project_id", "fingerprint", name="uq_project_dataset_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_filename: Mapped[str | None] = mapped_column(String(512))
    schema_version: Mapped[str] = mapped_column(String(32), default="1", nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    project: Mapped[ProjectRecord] = relationship(back_populates="datasets")
    seeds: Mapped[list[SeedExampleRecord]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan", passive_deletes=True
    )


class SeedExampleRecord(Base):
    __tablename__ = "seed_examples"
    __table_args__ = (
        UniqueConstraint("dataset_id", "fingerprint", name="uq_seed_dataset_fingerprint"),
        UniqueConstraint("dataset_id", "position", name="uq_seed_dataset_position"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    messages_json: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(256))
    root_seed_id: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    dataset: Mapped[DatasetRecord] = relationship(back_populates="seeds")


class RecipeRecord(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        UniqueConstraint("dataset_id", "fingerprint", name="uq_recipe_dataset_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    recipe_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class RunRecord(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(
        ForeignKey("datasets.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    recipe_id: Mapped[str] = mapped_column(
        ForeignKey("recipes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default=RunStatus.queued.value, nullable=False, index=True
    )
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_budget: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    needs_review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    recipe_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_fingerprint: Mapped[str | None] = mapped_column(String(64))
    provider_fingerprint: Mapped[str | None] = mapped_column(String(64))
    embedder_fingerprint: Mapped[str | None] = mapped_column(String(64))
    error_type: Mapped[str | None] = mapped_column(String(160))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    lease_owner: Mapped[str | None] = mapped_column(String(256))
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_epoch: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_type: Mapped[str | None] = mapped_column(String(160))
    error_message: Mapped[str | None] = mapped_column(Text)


class CandidateRecord(Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "candidate_fingerprint", name="uq_run_candidate_fingerprint"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    generation_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    messages_json: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_seed_ids_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    provider_trace_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    automated_decision: Mapped[str | None] = mapped_column(String(32), index=True)
    final_decision: Mapped[str | None] = mapped_column(String(32), index=True)
    quality_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class QualityReportRecord(Base):
    __tablename__ = "quality_reports"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    automated_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    final_decision: Mapped[str | None] = mapped_column(String(32))
    components_json: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, default=list, nullable=False
    )
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    explanations_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    nearest_match_id: Mapped[str | None] = mapped_column(String(128))
    nearest_similarity: Mapped[float | None] = mapped_column(Float)
    embedder_fingerprint: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ReviewRecord(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    candidate_id: Mapped[str] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    reviewer: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class ExportRecord(Base):
    __tablename__ = "exports"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), default="completed", nullable=False)
    output_path: Mapped[str] = mapped_column(String(1_024), nullable=False, unique=True)
    manifest_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    artifact_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class AuditEventRecord(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True, default=new_id)
    event_type: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(160), default="system", nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
