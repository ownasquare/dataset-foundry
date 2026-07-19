"""Focused repositories that keep transaction details out of product services."""

from __future__ import annotations

import builtins
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError

from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    ExportManifest,
    GeneratedCandidate,
    GenerationRecipe,
    QualityComponent,
    QualityReport,
    ReviewDecision,
    RunStatus,
    TrainingExample,
    validate_run_transition,
)
from dataset_foundry.ingestion.fingerprint import (
    fingerprint_candidate,
    fingerprint_example,
    fingerprint_mapping,
)
from dataset_foundry.persistence.database import SessionFactory, session_scope
from dataset_foundry.persistence.models import (
    AuditEventRecord,
    CandidateRecord,
    DatasetRecord,
    ExportRecord,
    JobRecord,
    ProjectRecord,
    QualityReportRecord,
    RecipeRecord,
    ReviewRecord,
    RunRecord,
    SeedExampleRecord,
)


class RecordNotFoundError(LookupError):
    """Raised when a requested persistent entity does not exist."""


class LeaseLostError(RuntimeError):
    """Raised when a worker mutates a job without current lease ownership."""


def _messages_payload(messages: list[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role.value, "content": message.content} for message in messages]


def _training_example(record: SeedExampleRecord) -> TrainingExample:
    return TrainingExample(
        id=record.id,
        messages=[ChatMessage.model_validate(message) for message in record.messages_json],
        metadata=record.metadata_json,
        source_id=record.source_id,
        root_seed_id=record.root_seed_id,
    )


class ProjectRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(
        self,
        *,
        name: str,
        description: str | None = None,
        project_id: str | None = None,
    ) -> ProjectRecord:
        if not name.strip():
            raise ValueError("project name must not be blank")
        with session_scope(self.session_factory) as session:
            record = ProjectRecord(
                id=project_id or uuid4().hex,
                name=name.strip(),
                description=description.strip() if description else None,
            )
            session.add(record)
            session.flush()
            return record

    def get(self, project_id: str) -> ProjectRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(ProjectRecord, project_id)
            if record is None:
                raise RecordNotFoundError(f"project {project_id} was not found")
            return record

    def list(self, *, limit: int = 100, offset: int = 0) -> list[ProjectRecord]:
        with session_scope(self.session_factory) as session:
            return list(
                session.scalars(
                    select(ProjectRecord)
                    .order_by(ProjectRecord.created_at.desc(), ProjectRecord.id)
                    .limit(limit)
                    .offset(offset)
                )
            )

    def list_datasets(self, project_id: str) -> builtins.list[DatasetRecord]:
        with session_scope(self.session_factory) as session:
            return list(
                session.scalars(
                    select(DatasetRecord)
                    .where(DatasetRecord.project_id == project_id)
                    .order_by(DatasetRecord.created_at.desc(), DatasetRecord.id)
                )
            )


class DatasetRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(
        self,
        *,
        project_id: str,
        name: str,
        fingerprint: str,
        examples: list[TrainingExample] | tuple[TrainingExample, ...],
        source_filename: str | None = None,
        metadata: dict[str, Any] | None = None,
        dataset_id: str | None = None,
    ) -> DatasetRecord:
        """Create one content-addressed dataset, returning an existing identical import."""

        with session_scope(self.session_factory) as session:
            existing = session.scalar(
                select(DatasetRecord).where(
                    DatasetRecord.project_id == project_id,
                    DatasetRecord.fingerprint == fingerprint,
                )
            )
            if existing is not None:
                return existing
            record = DatasetRecord(
                id=dataset_id or uuid4().hex,
                project_id=project_id,
                name=name,
                fingerprint=fingerprint,
                source_filename=source_filename,
                row_count=len(examples),
                metadata_json=metadata or {},
            )
            session.add(record)
            session.flush()
            for position, example in enumerate(examples):
                session.add(
                    SeedExampleRecord(
                        id=uuid4().hex,
                        dataset_id=record.id,
                        position=position,
                        fingerprint=fingerprint_example(example),
                        messages_json=_messages_payload(example.messages),
                        metadata_json=example.metadata,
                        source_id=example.source_id,
                        root_seed_id=example.root_seed_id,
                    )
                )
            session.flush()
            return record

    def get(self, dataset_id: str) -> DatasetRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(DatasetRecord, dataset_id)
            if record is None:
                raise RecordNotFoundError(f"dataset {dataset_id} was not found")
            return record

    def get_by_fingerprint(self, project_id: str, fingerprint: str) -> DatasetRecord | None:
        with session_scope(self.session_factory) as session:
            return session.scalar(
                select(DatasetRecord).where(
                    DatasetRecord.project_id == project_id,
                    DatasetRecord.fingerprint == fingerprint,
                )
            )

    def list(
        self,
        *,
        project_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DatasetRecord]:
        statement = (
            select(DatasetRecord)
            .order_by(DatasetRecord.created_at.desc(), DatasetRecord.id)
            .limit(limit)
            .offset(offset)
        )
        if project_id is not None:
            statement = statement.where(DatasetRecord.project_id == project_id)
        with session_scope(self.session_factory) as session:
            return list(session.scalars(statement))

    def list_examples(self, dataset_id: str) -> builtins.list[TrainingExample]:
        with session_scope(self.session_factory) as session:
            records = list(
                session.scalars(
                    select(SeedExampleRecord)
                    .where(SeedExampleRecord.dataset_id == dataset_id)
                    .order_by(SeedExampleRecord.position)
                )
            )
        return [_training_example(record) for record in records]

    def get_examples(
        self,
        dataset_id: str,
        example_ids: Collection[str],
    ) -> dict[str, TrainingExample]:
        identifiers = set(example_ids)
        if not identifiers:
            return {}
        with session_scope(self.session_factory) as session:
            records = session.scalars(
                select(SeedExampleRecord).where(
                    SeedExampleRecord.dataset_id == dataset_id,
                    SeedExampleRecord.id.in_(identifiers),
                )
            )
            return {record.id: _training_example(record) for record in records}


class RecipeRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, dataset_id: str, recipe: GenerationRecipe) -> RecipeRecord:
        normalized = recipe.model_copy(update={"dataset_id": dataset_id})
        payload = normalized.model_dump(mode="json")
        semantic_payload = normalized.model_dump(
            mode="json",
            exclude={"id", "created_at", "updated_at"},
        )
        fingerprint = fingerprint_mapping(semantic_payload)
        with session_scope(self.session_factory) as session:
            existing = session.scalar(
                select(RecipeRecord).where(
                    RecipeRecord.dataset_id == dataset_id,
                    RecipeRecord.fingerprint == fingerprint,
                )
            )
            if existing is not None:
                return existing
            record = RecipeRecord(
                id=normalized.id,
                dataset_id=dataset_id,
                name=normalized.name,
                fingerprint=fingerprint,
                recipe_json=payload,
            )
            session.add(record)
            session.flush()
            return record

    def get(self, recipe_id: str) -> RecipeRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(RecipeRecord, recipe_id)
            if record is None:
                raise RecordNotFoundError(f"recipe {recipe_id} was not found")
            return record

    def as_domain(self, recipe_id: str) -> GenerationRecipe:
        return GenerationRecipe.model_validate(self.get(recipe_id).recipe_json)

    def list(self, *, dataset_id: str | None = None) -> list[RecipeRecord]:
        statement = select(RecipeRecord).order_by(RecipeRecord.created_at.desc(), RecipeRecord.id)
        if dataset_id is not None:
            statement = statement.where(RecipeRecord.dataset_id == dataset_id)
        with session_scope(self.session_factory) as session:
            return list(session.scalars(statement))


class RunRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(
        self,
        *,
        dataset_id: str,
        recipe_id: str,
        target_count: int,
        candidate_budget: int,
        dataset_fingerprint: str,
        recipe_fingerprint: str,
        prompt_fingerprint: str | None = None,
        provider_fingerprint: str | None = None,
        embedder_fingerprint: str | None = None,
        run_id: str | None = None,
    ) -> RunRecord:
        with session_scope(self.session_factory) as session:
            record = RunRecord(
                id=run_id or uuid4().hex,
                dataset_id=dataset_id,
                recipe_id=recipe_id,
                target_count=target_count,
                candidate_budget=candidate_budget,
                dataset_fingerprint=dataset_fingerprint,
                recipe_fingerprint=recipe_fingerprint,
                prompt_fingerprint=prompt_fingerprint,
                provider_fingerprint=provider_fingerprint,
                embedder_fingerprint=embedder_fingerprint,
            )
            session.add(record)
            session.flush()
            return record

    def get(self, run_id: str) -> RunRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                raise RecordNotFoundError(f"run {run_id} was not found")
            return record

    def list(self, *, dataset_id: str | None = None, limit: int = 100) -> list[RunRecord]:
        statement = (
            select(RunRecord).order_by(RunRecord.created_at.desc(), RunRecord.id).limit(limit)
        )
        if dataset_id is not None:
            statement = statement.where(RunRecord.dataset_id == dataset_id)
        with session_scope(self.session_factory) as session:
            return list(session.scalars(statement))

    def transition(self, run_id: str, target: RunStatus) -> RunRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                raise RecordNotFoundError(f"run {run_id} was not found")
            current = RunStatus(record.status)
            validate_run_transition(current, target)
            now = datetime.now(UTC)
            record.status = target.value
            record.updated_at = now
            if target is RunStatus.running and record.started_at is None:
                record.started_at = now
            if target in {RunStatus.completed, RunStatus.failed, RunStatus.cancelled}:
                record.finished_at = now
            session.flush()
            return record

    def update_counts(
        self,
        run_id: str,
        *,
        generated_count: int,
        accepted_count: int,
        rejected_count: int,
        needs_review_count: int,
    ) -> RunRecord:
        if accepted_count + rejected_count + needs_review_count > generated_count:
            raise ValueError("classified candidate counts cannot exceed generated_count")
        with session_scope(self.session_factory) as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                raise RecordNotFoundError(f"run {run_id} was not found")
            if generated_count > record.candidate_budget:
                raise ValueError("generated_count cannot exceed candidate_budget")
            record.generated_count = generated_count
            record.accepted_count = accepted_count
            record.rejected_count = rejected_count
            record.needs_review_count = needs_review_count
            record.updated_at = datetime.now(UTC)
            session.flush()
            return record

    def record_failure(self, run_id: str, error: Exception) -> RunRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(RunRecord, run_id)
            if record is None:
                raise RecordNotFoundError(f"run {run_id} was not found")
            record.error_type = type(error).__name__[:160]
            record.error_message = str(error)[:4_000]
            session.flush()
            return record


@dataclass(frozen=True, slots=True)
class LeaseClaim:
    job_id: str
    run_id: str
    worker_id: str
    token: str
    epoch: int
    expires_at: datetime


class JobRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def enqueue(
        self, run_id: str, *, max_attempts: int = 3, job_id: str | None = None
    ) -> JobRecord:
        if not 1 <= max_attempts <= 10:
            raise ValueError("max_attempts must be between 1 and 10")
        with session_scope(self.session_factory) as session:
            existing = session.scalar(select(JobRecord).where(JobRecord.run_id == run_id))
            if existing is not None:
                return existing
            record = JobRecord(
                id=job_id or uuid4().hex,
                run_id=run_id,
                max_attempts=max_attempts,
            )
            session.add(record)
            session.flush()
            return record

    def get(self, job_id: str) -> JobRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(JobRecord, job_id)
            if record is None:
                raise RecordNotFoundError(f"job {job_id} was not found")
            return record

    def claim_next(self, worker_id: str, *, lease_seconds: int = 300) -> LeaseClaim | None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be blank")
        if not 10 <= lease_seconds <= 3_600:
            raise ValueError("lease_seconds must be between 10 and 3600")
        now = datetime.now(UTC)
        with session_scope(self.session_factory) as session:
            candidate = session.scalar(
                select(JobRecord)
                .where(
                    or_(
                        JobRecord.status == "queued",
                        (JobRecord.status == "running") & (JobRecord.lease_expires_at <= now),
                    ),
                    JobRecord.attempts < JobRecord.max_attempts,
                )
                .order_by(JobRecord.queued_at, JobRecord.id)
                .limit(1)
            )
            if candidate is None:
                return None
            token = uuid4().hex
            expires_at = now + timedelta(seconds=lease_seconds)
            original_epoch = candidate.lease_epoch
            claimed = session.execute(
                update(JobRecord)
                .where(
                    JobRecord.id == candidate.id,
                    JobRecord.lease_epoch == original_epoch,
                    or_(
                        JobRecord.status == "queued",
                        (JobRecord.status == "running") & (JobRecord.lease_expires_at <= now),
                    ),
                )
                .values(
                    status="running",
                    attempts=JobRecord.attempts + 1,
                    lease_owner=worker_id,
                    lease_token=token,
                    lease_epoch=JobRecord.lease_epoch + 1,
                    lease_expires_at=expires_at,
                    heartbeat_at=now,
                    started_at=now,
                )
            )
            if not isinstance(claimed, CursorResult) or claimed.rowcount != 1:
                return None
            return LeaseClaim(
                job_id=candidate.id,
                run_id=candidate.run_id,
                worker_id=worker_id,
                token=token,
                epoch=original_epoch + 1,
                expires_at=expires_at,
            )

    def renew(self, claim: LeaseClaim, *, lease_seconds: int = 300) -> LeaseClaim:
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=lease_seconds)
        with session_scope(self.session_factory) as session:
            result = session.execute(
                update(JobRecord)
                .where(
                    JobRecord.id == claim.job_id,
                    JobRecord.lease_owner == claim.worker_id,
                    JobRecord.lease_token == claim.token,
                    JobRecord.lease_epoch == claim.epoch,
                    JobRecord.status == "running",
                    JobRecord.lease_expires_at > now,
                )
                .values(lease_expires_at=expires_at, heartbeat_at=now)
            )
            if not isinstance(result, CursorResult) or result.rowcount != 1:
                raise LeaseLostError("job lease is no longer active")
        return LeaseClaim(
            job_id=claim.job_id,
            run_id=claim.run_id,
            worker_id=claim.worker_id,
            token=claim.token,
            epoch=claim.epoch,
            expires_at=expires_at,
        )

    def finish(self, claim: LeaseClaim, *, status: str = "completed") -> JobRecord:
        if status not in {"completed", "failed", "cancelled"}:
            raise ValueError("terminal job status must be completed, failed, or cancelled")
        now = datetime.now(UTC)
        with session_scope(self.session_factory) as session:
            record = session.get(JobRecord, claim.job_id)
            if record is None:
                raise RecordNotFoundError(f"job {claim.job_id} was not found")
            if (
                record.lease_owner != claim.worker_id
                or record.lease_token != claim.token
                or record.lease_epoch != claim.epoch
                or record.status != "running"
            ):
                raise LeaseLostError("job lease is no longer owned by this worker")
            record.status = status
            record.heartbeat_at = now
            record.finished_at = now
            record.lease_owner = None
            record.lease_token = None
            record.lease_expires_at = None
            session.flush()
            return record

    def fail(self, claim: LeaseClaim, error: Exception, *, retryable: bool) -> JobRecord:
        now = datetime.now(UTC)
        with session_scope(self.session_factory) as session:
            record = session.get(JobRecord, claim.job_id)
            if record is None:
                raise RecordNotFoundError(f"job {claim.job_id} was not found")
            if record.lease_token != claim.token or record.lease_epoch != claim.epoch:
                raise LeaseLostError("job lease is no longer owned by this worker")
            record.error_type = type(error).__name__[:160]
            record.error_message = str(error)[:4_000]
            record.heartbeat_at = now
            terminal = not retryable or record.attempts >= record.max_attempts
            record.status = "failed" if terminal else "queued"
            record.finished_at = now if terminal else None
            record.lease_owner = None
            record.lease_token = None
            record.lease_expires_at = None
            session.flush()
            return record

    def recover_expired(self) -> int:
        now = datetime.now(UTC)
        with session_scope(self.session_factory) as session:
            result = session.execute(
                update(JobRecord)
                .where(
                    JobRecord.status == "running",
                    JobRecord.lease_expires_at <= now,
                    JobRecord.attempts < JobRecord.max_attempts,
                )
                .values(
                    status="queued",
                    lease_owner=None,
                    lease_token=None,
                    lease_expires_at=None,
                )
            )
            return result.rowcount if isinstance(result, CursorResult) else 0


class CandidateRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def add(
        self,
        run_id: str,
        candidate: GeneratedCandidate,
        *,
        fingerprint: str | None = None,
    ) -> tuple[CandidateRecord, bool]:
        candidate_fingerprint = (
            fingerprint or candidate.candidate_fingerprint or fingerprint_candidate(candidate)
        )
        with session_scope(self.session_factory) as session:
            existing = session.scalar(
                select(CandidateRecord).where(
                    CandidateRecord.run_id == run_id,
                    CandidateRecord.candidate_fingerprint == candidate_fingerprint,
                )
            )
            if existing is not None:
                return existing, False
            record = CandidateRecord(
                id=candidate.id,
                run_id=run_id,
                candidate_fingerprint=candidate_fingerprint,
                generation_index=candidate.generation_index,
                messages_json=_messages_payload(candidate.messages),
                metadata_json=candidate.metadata,
                source_seed_ids_json=candidate.source_seed_ids,
                provider_trace_json=candidate.provider_trace.model_dump(mode="json"),
            )
            session.add(record)
            try:
                session.flush()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(CandidateRecord).where(
                        CandidateRecord.run_id == run_id,
                        CandidateRecord.candidate_fingerprint == candidate_fingerprint,
                    )
                )
                if existing is None:
                    raise
                return existing, False
            return record, True

    def get(self, candidate_id: str) -> CandidateRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(CandidateRecord, candidate_id)
            if record is None:
                raise RecordNotFoundError(f"candidate {candidate_id} was not found")
            return record

    def list(
        self,
        run_id: str,
        *,
        decision: CandidateDecision | None = None,
        limit: int = 1_000,
        offset: int = 0,
        after_generation_index: int | None = None,
        after_id: str | None = None,
    ) -> list[CandidateRecord]:
        statement = (
            select(CandidateRecord)
            .where(CandidateRecord.run_id == run_id)
            .order_by(CandidateRecord.generation_index, CandidateRecord.id)
        )
        if decision is not None:
            statement = statement.where(
                or_(
                    CandidateRecord.final_decision == decision.value,
                    (CandidateRecord.final_decision.is_(None))
                    & (CandidateRecord.automated_decision == decision.value),
                )
            )
        if after_generation_index is not None:
            if after_id is None:
                raise ValueError("after_id is required with after_generation_index")
            statement = statement.where(
                or_(
                    CandidateRecord.generation_index > after_generation_index,
                    and_(
                        CandidateRecord.generation_index == after_generation_index,
                        CandidateRecord.id > after_id,
                    ),
                )
            )
        statement = statement.limit(limit).offset(offset)
        with session_scope(self.session_factory) as session:
            return list(session.scalars(statement))

    def save_quality_report(self, report: QualityReport) -> QualityReportRecord:
        with session_scope(self.session_factory) as session:
            candidate = session.get(CandidateRecord, report.candidate_id)
            if candidate is None:
                raise RecordNotFoundError(f"candidate {report.candidate_id} was not found")
            existing = session.scalar(
                select(QualityReportRecord).where(
                    QualityReportRecord.candidate_id == report.candidate_id
                )
            )
            values = {
                "score": report.score,
                "automated_decision": report.automated_decision.value,
                "final_decision": report.final_decision.value if report.final_decision else None,
                "components_json": [
                    component.model_dump(mode="json") for component in report.components
                ],
                "reason_codes_json": report.reason_codes,
                "explanations_json": report.explanations,
                "nearest_match_id": report.nearest_match_id,
                "nearest_similarity": report.nearest_similarity,
                "embedder_fingerprint": report.embedder_fingerprint,
            }
            if existing is None:
                existing = QualityReportRecord(candidate_id=report.candidate_id, **values)
                session.add(existing)
            else:
                for name, value in values.items():
                    setattr(existing, name, value)
            candidate.quality_score = report.score
            candidate.automated_decision = report.automated_decision.value
            candidate.final_decision = (
                report.final_decision.value if report.final_decision else None
            )
            session.flush()
            return existing

    def get_quality_report(self, candidate_id: str) -> QualityReport | None:
        with session_scope(self.session_factory) as session:
            record = session.scalar(
                select(QualityReportRecord).where(QualityReportRecord.candidate_id == candidate_id)
            )
            if record is None:
                return None
            return QualityReport(
                candidate_id=record.candidate_id,
                score=record.score,
                automated_decision=CandidateDecision(record.automated_decision),
                final_decision=(
                    CandidateDecision(record.final_decision) if record.final_decision else None
                ),
                components=[
                    QualityComponent.model_validate(component)
                    for component in record.components_json
                ],
                reason_codes=record.reason_codes_json,
                explanations=record.explanations_json,
                nearest_match_id=record.nearest_match_id,
                nearest_similarity=record.nearest_similarity,
                embedder_fingerprint=record.embedder_fingerprint,
                created_at=record.created_at,
            )


class ReviewRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def record(self, review: ReviewDecision) -> ReviewRecord:
        with session_scope(self.session_factory) as session:
            candidate = session.get(CandidateRecord, review.candidate_id)
            if candidate is None:
                raise RecordNotFoundError(f"candidate {review.candidate_id} was not found")
            record = ReviewRecord(
                candidate_id=review.candidate_id,
                decision=review.decision.value,
                note=review.note,
                reviewer=review.reviewer,
                created_at=review.created_at,
            )
            candidate.final_decision = review.decision.value
            quality = session.scalar(
                select(QualityReportRecord).where(
                    QualityReportRecord.candidate_id == review.candidate_id
                )
            )
            if quality is not None:
                quality.final_decision = review.decision.value
            session.add(record)
            session.add(
                AuditEventRecord(
                    event_type="candidate.reviewed",
                    entity_type="candidate",
                    entity_id=review.candidate_id,
                    actor=review.reviewer,
                    payload_json={"decision": review.decision.value, "note": review.note},
                )
            )
            # Flush the new effective decision before calculating aggregates, then
            # persist the review, candidate/report decision, audit event, and run
            # counts in this same transaction.
            session.flush()
            effective_decision = func.coalesce(
                CandidateRecord.final_decision,
                CandidateRecord.automated_decision,
            )
            counts = session.execute(
                select(
                    func.count(CandidateRecord.id).label("generated_count"),
                    func.sum(
                        case(
                            (effective_decision == CandidateDecision.accepted.value, 1),
                            else_=0,
                        )
                    ).label("accepted_count"),
                    func.sum(
                        case(
                            (effective_decision == CandidateDecision.rejected.value, 1),
                            else_=0,
                        )
                    ).label("rejected_count"),
                    func.sum(
                        case(
                            (effective_decision == CandidateDecision.needs_review.value, 1),
                            else_=0,
                        )
                    ).label("needs_review_count"),
                ).where(CandidateRecord.run_id == candidate.run_id)
            ).one()
            run = session.get(RunRecord, candidate.run_id)
            if run is None:
                raise RecordNotFoundError(f"run {candidate.run_id} was not found")
            run.generated_count = int(counts.generated_count or 0)
            run.accepted_count = int(counts.accepted_count or 0)
            run.rejected_count = int(counts.rejected_count or 0)
            run.needs_review_count = int(counts.needs_review_count or 0)
            run.updated_at = datetime.now(UTC)
            session.flush()
            return record

    def list(self, candidate_id: str) -> list[ReviewRecord]:
        with session_scope(self.session_factory) as session:
            return list(
                session.scalars(
                    select(ReviewRecord)
                    .where(ReviewRecord.candidate_id == candidate_id)
                    .order_by(ReviewRecord.created_at, ReviewRecord.id)
                )
            )


class ExportRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def create(self, manifest: ExportManifest, output_path: str | Path) -> ExportRecord:
        manifest_payload = manifest.model_dump(mode="json")
        artifact_hash = fingerprint_mapping(manifest_payload)
        with session_scope(self.session_factory) as session:
            record = ExportRecord(
                id=manifest.export_id,
                run_id=manifest.run_id,
                output_path=str(output_path),
                manifest_json=manifest_payload,
                artifact_hash=artifact_hash,
            )
            session.add(record)
            session.flush()
            return record

    def get(self, export_id: str) -> ExportRecord:
        with session_scope(self.session_factory) as session:
            record = session.get(ExportRecord, export_id)
            if record is None:
                raise RecordNotFoundError(f"export {export_id} was not found")
            return record

    def list(self, run_id: str) -> list[ExportRecord]:
        with session_scope(self.session_factory) as session:
            return list(
                session.scalars(
                    select(ExportRecord)
                    .where(ExportRecord.run_id == run_id)
                    .order_by(ExportRecord.created_at.desc(), ExportRecord.id)
                )
            )


class AuditRepository:
    def __init__(self, session_factory: SessionFactory) -> None:
        self.session_factory = session_factory

    def record(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_id: str,
        actor: str = "system",
        payload: dict[str, Any] | None = None,
    ) -> AuditEventRecord:
        with session_scope(self.session_factory) as session:
            record = AuditEventRecord(
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                actor=actor,
                payload_json=payload or {},
            )
            session.add(record)
            session.flush()
            return record

    def list(self, *, entity_id: str | None = None, limit: int = 1_000) -> list[AuditEventRecord]:
        statement = select(AuditEventRecord).order_by(
            AuditEventRecord.created_at.desc(), AuditEventRecord.id
        )
        if entity_id is not None:
            statement = statement.where(AuditEventRecord.entity_id == entity_id)
        with session_scope(self.session_factory) as session:
            return list(session.scalars(statement.limit(limit)))


class Repositories:
    """Convenient dependency bundle with no hidden global session."""

    def __init__(self, session_factory: SessionFactory) -> None:
        self.projects = ProjectRepository(session_factory)
        self.datasets = DatasetRepository(session_factory)
        self.recipes = RecipeRepository(session_factory)
        self.runs = RunRepository(session_factory)
        self.jobs = JobRepository(session_factory)
        self.candidates = CandidateRepository(session_factory)
        self.reviews = ReviewRepository(session_factory)
        self.exports = ExportRepository(session_factory)
        self.audit = AuditRepository(session_factory)
