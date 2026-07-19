"""Bounded generation orchestration across providers, quality, and persistence."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Callable
from typing import Protocol

from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    GeneratedCandidate,
    GenerationBatchRequest,
    ProviderTrace,
    RunStatus,
    TrainingExample,
)
from dataset_foundry.generation.prompts import PROMPT_VERSION
from dataset_foundry.persistence import Repositories
from dataset_foundry.persistence.models import CandidateRecord, RunRecord
from dataset_foundry.providers import ProviderRegistry
from dataset_foundry.quality import QualityPipeline


class CandidateBudgetExhaustedError(RuntimeError):
    """The bounded generation plan ended before enough candidates were accepted."""


class QualityPipelineFactory(Protocol):
    """Construct the per-run quality pipeline used by the durable worker."""

    def __call__(
        self,
        *,
        quality_threshold: float,
        similarity_threshold: float,
    ) -> QualityPipeline:
        """Return a configured pipeline for one persisted recipe."""


def default_quality_pipeline_factory(
    *,
    quality_threshold: float,
    similarity_threshold: float,
) -> QualityPipeline:
    """Build the default explainable scorer and lexical-similarity pipeline."""

    return QualityPipeline(
        quality_threshold=quality_threshold,
        similarity_threshold=similarity_threshold,
    )


_MAX_PROVIDER_SEEDS = 100


def select_batch_seeds(
    seeds: list[TrainingExample],
    *,
    random_seed: int,
    batch_index: int,
    limit: int = _MAX_PROVIDER_SEEDS,
) -> list[TrainingExample]:
    """Return a deterministic, rotating sample spanning the complete seed dataset.

    Provider requests intentionally cap seed context at 100 examples. For larger
    datasets, divide the stable persisted order into ``limit`` non-overlapping
    strata and select one example from each stratum. The recipe seed establishes
    each stratum's starting point, while the batch index rotates that selection.
    This keeps every request representative, eventually exposes every seed, and
    makes retries and resumed runs replay the same lineage exactly.
    """

    if limit < 1:
        raise ValueError("seed selection limit must be positive")
    if batch_index < 0:
        raise ValueError("batch index must not be negative")
    if len(seeds) <= limit:
        return list(seeds)

    selected: list[TrainingExample] = []
    seed_count = len(seeds)
    for stratum_index in range(limit):
        start = stratum_index * seed_count // limit
        stop = (stratum_index + 1) * seed_count // limit
        width = stop - start
        offset_digest = hashlib.sha256(f"{random_seed}:{stratum_index}".encode()).digest()
        initial_offset = int.from_bytes(offset_digest[:8], byteorder="big") % width
        selected.append(seeds[start + (initial_offset + batch_index) % width])
    return selected


def candidate_from_record(record: CandidateRecord) -> GeneratedCandidate:
    """Rehydrate one persisted candidate without leaking ORM objects into services."""

    return GeneratedCandidate(
        id=record.id,
        messages=[ChatMessage.model_validate(message) for message in record.messages_json],
        metadata=record.metadata_json,
        source_seed_ids=record.source_seed_ids_json,
        generation_index=record.generation_index,
        provider_trace=ProviderTrace.model_validate(record.provider_trace_json),
        candidate_fingerprint=record.candidate_fingerprint,
    )


class GenerationService:
    """Create queued runs and execute their deterministic, bounded generation loop."""

    def __init__(
        self,
        repositories: Repositories,
        providers: ProviderRegistry,
        *,
        quality_pipeline_factory: QualityPipelineFactory | None = None,
    ) -> None:
        self.repositories = repositories
        self.providers = providers
        self.quality_pipeline_factory = quality_pipeline_factory or default_quality_pipeline_factory

    def enqueue(self, *, dataset_id: str, recipe_id: str) -> RunRecord:
        dataset = self.repositories.datasets.get(dataset_id)
        recipe_record = self.repositories.recipes.get(recipe_id)
        recipe = self.repositories.recipes.as_domain(recipe_id)
        if recipe_record.dataset_id != dataset_id:
            raise ValueError("recipe and dataset must belong to the same dataset snapshot")
        prompt_fingerprint = hashlib.sha256(PROMPT_VERSION.encode()).hexdigest()
        provider_fingerprint = hashlib.sha256(
            f"{recipe.provider.value}:{recipe.model}".encode()
        ).hexdigest()
        run = self.repositories.runs.create(
            dataset_id=dataset_id,
            recipe_id=recipe_id,
            target_count=recipe.target_count,
            candidate_budget=recipe.candidate_budget,
            dataset_fingerprint=dataset.fingerprint,
            recipe_fingerprint=recipe_record.fingerprint,
            prompt_fingerprint=prompt_fingerprint,
            provider_fingerprint=provider_fingerprint,
        )
        self.repositories.jobs.enqueue(run.id, max_attempts=max(1, recipe.max_retries + 1))
        self.repositories.audit.record(
            event_type="run.queued",
            entity_type="run",
            entity_id=run.id,
            payload={
                "dataset_id": dataset_id,
                "recipe_id": recipe_id,
                "candidate_budget": recipe.candidate_budget,
            },
        )
        return run

    async def process(
        self,
        run_id: str,
        *,
        heartbeat: Callable[[], None] | None = None,
    ) -> RunRecord:
        run = self.repositories.runs.get(run_id)
        if run.status in {RunStatus.completed.value, RunStatus.cancelled.value}:
            return run
        if run.status == RunStatus.queued.value:
            run = self.repositories.runs.transition(run_id, RunStatus.running)
            self.repositories.audit.record(
                event_type="run.started",
                entity_type="run",
                entity_id=run_id,
            )
        if run.status != RunStatus.running.value:
            raise ValueError(f"run {run_id} is not processable from status {run.status}")

        recipe = self.repositories.recipes.as_domain(run.recipe_id)
        seeds = self.repositories.datasets.list_examples(run.dataset_id)
        if not seeds:
            raise ValueError("run dataset contains no seed examples")
        provider = self.providers.get(recipe.provider, recipe.model)
        quality = self.quality_pipeline_factory(
            quality_threshold=recipe.quality_threshold,
            similarity_threshold=recipe.similarity_threshold,
        )

        records = self.repositories.candidates.list(run_id, limit=recipe.candidate_budget)
        candidates = [candidate_from_record(record) for record in records]
        accepted_before_recovery = [
            item
            for existing, item in zip(records, candidates, strict=True)
            if (existing.final_decision or existing.automated_decision)
            == CandidateDecision.accepted.value
        ]
        pending = [
            candidate
            for record, candidate in zip(records, candidates, strict=True)
            if record.automated_decision is None
        ]
        for report in quality.evaluate_many(
            pending,
            seeds=seeds,
            accepted=accepted_before_recovery,
            constraints=recipe.constraints,
        ):
            self.repositories.candidates.save_quality_report(report)

        records = self.repositories.candidates.list(run_id, limit=recipe.candidate_budget)
        accepted = [
            candidate_from_record(record)
            for record in records
            if (record.final_decision or record.automated_decision)
            == CandidateDecision.accepted.value
        ]
        counts = _counts(records)
        run = self.repositories.runs.update_counts(run_id, **counts)
        next_batch_index = (
            max((record.generation_index for record in records), default=-1) // recipe.batch_size
            + 1
        )
        call_budget = math.ceil(recipe.candidate_budget / recipe.batch_size)

        while (
            run.accepted_count < recipe.target_count
            and run.generated_count < recipe.candidate_budget
            and next_batch_index < call_budget
        ):
            latest = self.repositories.runs.get(run_id)
            if latest.status == RunStatus.cancelled.value:
                return latest
            remaining_budget = recipe.candidate_budget - run.generated_count
            requested_count = min(recipe.batch_size, remaining_budget)
            batch_seeds = select_batch_seeds(
                seeds,
                random_seed=recipe.random_seed,
                batch_index=next_batch_index,
            )
            batch = await provider.generate_batch(
                GenerationBatchRequest(
                    run_id=run_id,
                    recipe=recipe,
                    seed_examples=batch_seeds,
                    batch_index=next_batch_index,
                    requested_count=requested_count,
                )
            )
            next_batch_index += 1
            created_count = 0
            reports = quality.evaluate_many(
                batch.candidates,
                seeds=seeds,
                accepted=accepted,
                constraints=recipe.constraints,
            )
            for candidate, report in zip(batch.candidates, reports, strict=True):
                record, created = self.repositories.candidates.add(run_id, candidate)
                if not created:
                    continue
                created_count += 1
                self.repositories.candidates.save_quality_report(report)
                if report.decision is CandidateDecision.accepted:
                    accepted.append(candidate)
                records.append(record)
                if len(accepted) >= recipe.target_count:
                    break

            records = self.repositories.candidates.list(run_id, limit=recipe.candidate_budget)
            counts = _counts(records)
            run = self.repositories.runs.update_counts(run_id, **counts)
            self.repositories.audit.record(
                event_type="run.batch_completed",
                entity_type="run",
                entity_id=run_id,
                payload={
                    "batch_index": next_batch_index - 1,
                    "requested_count": requested_count,
                    "created_count": created_count,
                    "generated_count": run.generated_count,
                    "accepted_count": run.accepted_count,
                },
            )
            if heartbeat:
                heartbeat()

        if run.accepted_count < recipe.target_count:
            raise CandidateBudgetExhaustedError(
                f"accepted {run.accepted_count} of {recipe.target_count} target examples "
                f"within the {recipe.candidate_budget}-candidate budget"
            )
        completed = self.repositories.runs.transition(run_id, RunStatus.completed)
        self.repositories.audit.record(
            event_type="run.completed",
            entity_type="run",
            entity_id=run_id,
            payload={
                "generated_count": completed.generated_count,
                "accepted_count": completed.accepted_count,
            },
        )
        return completed


def _counts(records: list[CandidateRecord]) -> dict[str, int]:
    counts = {
        "generated_count": len(records),
        "accepted_count": 0,
        "rejected_count": 0,
        "needs_review_count": 0,
    }
    for record in records:
        decision = record.final_decision or record.automated_decision
        if decision == CandidateDecision.accepted.value:
            counts["accepted_count"] += 1
        elif decision == CandidateDecision.rejected.value:
            counts["rejected_count"] += 1
        elif decision == CandidateDecision.needs_review.value:
            counts["needs_review_count"] += 1
    return counts
