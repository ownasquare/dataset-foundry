from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    GeneratedCandidate,
    GenerationRecipe,
    ProviderName,
    ProviderTrace,
    QualityReport,
    ReviewDecision,
    RunStatus,
    TrainingExample,
)
from dataset_foundry.ingestion import fingerprint_dataset
from dataset_foundry.persistence import Database, DatasetRecord, Repositories


def examples() -> list[TrainingExample]:
    return [
        TrainingExample(
            id="seed-1",
            messages=[
                ChatMessage(role="user", content="How should support handle a late shipment?"),
                ChatMessage(
                    role="assistant",
                    content="Verify the address and carrier status, then provide a revised window.",
                ),
            ],
            metadata={"category": "shipping"},
        ),
        TrainingExample(
            id="seed-2",
            messages=[
                ChatMessage(role="user", content="How should support handle a duplicate charge?"),
                ChatMessage(
                    role="assistant",
                    content=(
                        "Check for a temporary authorization and investigate if both charges post."
                    ),
                ),
            ],
            metadata={"category": "billing"},
        ),
    ]


def make_candidate() -> GeneratedCandidate:
    return GeneratedCandidate(
        id="candidate-1",
        messages=[
            ChatMessage(role="user", content="A refund is late. What should support verify?"),
            ChatMessage(
                role="assistant",
                content=(
                    "Confirm the approval date, original payment method, and "
                    "bank processing window."
                ),
            ),
        ],
        source_seed_ids=["seed-2"],
        provider_trace=ProviderTrace(
            provider=ProviderName.offline,
            model="offline-deterministic-v1",
            mode="offline-deterministic",
        ),
    )


def test_repository_round_trip_idempotency_review_and_job_lease(tmp_path: Path) -> None:
    database = Database(tmp_path / "foundry.sqlite3")
    database.initialize()
    repositories = Repositories(database.session_factory)
    seed_examples = examples()
    dataset_fingerprint = fingerprint_dataset(seed_examples)

    project = repositories.projects.create(name="Support data", description="Synthetic QA")
    dataset = repositories.datasets.create(
        project_id=project.id,
        name="Support seeds",
        fingerprint=dataset_fingerprint,
        examples=seed_examples,
        source_filename="seeds.jsonl",
    )
    duplicate_import = repositories.datasets.create(
        project_id=project.id,
        name="Same content",
        fingerprint=dataset_fingerprint,
        examples=seed_examples,
    )
    assert duplicate_import.id == dataset.id
    assert len(repositories.datasets.list_examples(dataset.id)) == 2
    assert repositories.projects.list_datasets(project.id)[0].id == dataset.id

    second_project = repositories.projects.create(name="Second project")
    second_dataset = repositories.datasets.create(
        project_id=second_project.id,
        name="Reusable support seeds",
        fingerprint=dataset_fingerprint,
        examples=seed_examples,
    )
    assert second_dataset.id != dataset.id

    recipe = GenerationRecipe(name="Support variations", target_count=10, batch_size=2)
    recipe_record = repositories.recipes.create(dataset.id, recipe)
    equivalent_recipe = GenerationRecipe(
        id="different-generated-id",
        name="Support variations",
        target_count=10,
        batch_size=2,
    )
    equivalent_record = repositories.recipes.create(dataset.id, equivalent_recipe)
    assert equivalent_record.id == recipe_record.id
    assert len(repositories.recipes.list(dataset_id=dataset.id)) == 1
    run = repositories.runs.create(
        dataset_id=dataset.id,
        recipe_id=recipe_record.id,
        target_count=recipe.target_count,
        candidate_budget=recipe.candidate_budget,
        dataset_fingerprint=dataset.fingerprint,
        recipe_fingerprint=recipe_record.fingerprint,
    )
    repositories.runs.transition(run.id, RunStatus.running)

    job = repositories.jobs.enqueue(run.id)
    claim = repositories.jobs.claim_next("worker-test", lease_seconds=30)
    assert claim is not None and claim.job_id == job.id
    repositories.jobs.finish(claim)
    assert repositories.jobs.get(job.id).status == "completed"

    candidate = make_candidate()
    stored, created = repositories.candidates.add(run.id, candidate)
    duplicate, duplicate_created = repositories.candidates.add(run.id, candidate)
    assert created
    assert not duplicate_created
    assert duplicate.id == stored.id

    report = QualityReport(
        candidate_id=candidate.id,
        score=0.88,
        automated_decision=CandidateDecision.accepted,
    )
    repositories.candidates.save_quality_report(report)
    loaded_report = repositories.candidates.get_quality_report(candidate.id)
    assert loaded_report is not None and loaded_report.score == pytest.approx(0.88)
    repositories.reviews.record(
        ReviewDecision(
            candidate_id=candidate.id,
            decision=CandidateDecision.rejected,
            note="Human reviewer found an unsupported policy statement.",
        )
    )
    assert repositories.candidates.get(candidate.id).final_decision == "rejected"
    reviewed_run = repositories.runs.get(run.id)
    assert reviewed_run.generated_count == 1
    assert reviewed_run.accepted_count == 0
    assert reviewed_run.rejected_count == 1
    assert reviewed_run.needs_review_count == 0
    assert repositories.audit.list(entity_id=candidate.id)[0].event_type == "candidate.reviewed"
    database.dispose()


def test_sqlite_foreign_keys_are_enforced(tmp_path: Path) -> None:
    database = Database(tmp_path / "foreign-keys.sqlite3")
    database.initialize()

    with pytest.raises(IntegrityError), database.session() as session:
        session.add(
            DatasetRecord(
                id="orphan",
                project_id="missing-project",
                name="Orphan",
                fingerprint="a" * 64,
                row_count=0,
            )
        )
    database.dispose()


def test_worker_heartbeat_status_expires_and_stops(tmp_path: Path) -> None:
    database = Database(tmp_path / "worker-heartbeats.sqlite3")
    database.initialize()
    repositories = Repositories(database.session_factory)
    started_at = datetime(2026, 7, 18, 12, tzinfo=UTC)

    missing = repositories.workers.status(now=started_at)
    assert missing.ready is False
    assert missing.state == "missing"

    repositories.workers.heartbeat(
        "worker-a",
        state="idle",
        ttl_seconds=30,
        now=started_at,
    )
    idle = repositories.workers.status(now=started_at + timedelta(seconds=10))
    assert idle.ready is True
    assert idle.state == "idle"
    assert idle.worker_id == "worker-a"

    repositories.workers.heartbeat(
        "worker-a",
        state="busy",
        current_job_id="job-123",
        ttl_seconds=30,
        now=started_at + timedelta(seconds=20),
    )
    busy = repositories.workers.status(now=started_at + timedelta(seconds=21))
    assert busy.ready is True
    assert busy.state == "busy"
    assert busy.current_job_id == "job-123"

    stale = repositories.workers.status(now=started_at + timedelta(seconds=51))
    assert stale.ready is False
    assert stale.state == "stale"

    repositories.workers.stop("worker-a", now=started_at + timedelta(seconds=52))
    stopped = repositories.workers.status(now=started_at + timedelta(seconds=52))
    assert stopped.ready is False
    assert stopped.state == "stopped"
    assert stopped.current_job_id is None
    database.dispose()
