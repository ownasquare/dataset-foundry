"""Application dependency assembly with explicit lifecycle ownership."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from functools import lru_cache
from uuid import uuid4

from dataset_foundry.config import Settings, get_settings
from dataset_foundry.domain import CandidateDecision, ExportFormat, RunStatus
from dataset_foundry.exports import ExportService
from dataset_foundry.generation.service import (
    GenerationService,
    QualityPipelineFactory,
    candidate_from_record,
)
from dataset_foundry.jobs import Worker
from dataset_foundry.persistence import Database, Repositories
from dataset_foundry.persistence.models import ExportRecord
from dataset_foundry.providers import ProviderRegistry


class Container:
    """Own database, repositories, providers, and application services."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        quality_pipeline_factory: QualityPipelineFactory | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.settings.data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.database = Database(self.settings.resolved_database_url)
        self.database.initialize()
        self.repositories = Repositories(self.database.session_factory)
        self.providers = ProviderRegistry(self.settings)
        self.generation = GenerationService(
            self.repositories,
            self.providers,
            quality_pipeline_factory=quality_pipeline_factory,
        )
        self.exports = ExportService(self.settings.resolved_artifacts_dir)

    def worker(self, *, worker_id: str | None = None) -> Worker:
        return Worker(
            self.repositories,
            self.generation,
            worker_id=worker_id or self.settings.worker_id,
            lease_seconds=self.settings.worker_lease_seconds,
            heartbeat_seconds=self.settings.worker_heartbeat_seconds,
            poll_seconds=self.settings.worker_poll_seconds,
        )

    def create_export(
        self,
        run_id: str,
        *,
        export_id: str | None = None,
        name: str = "Dataset export",
        formats: Sequence[ExportFormat] | None = None,
        split_ratios: Mapping[str, float] | None = None,
    ) -> ExportRecord:
        run = self.repositories.runs.get(run_id)
        if run.status != RunStatus.completed.value:
            raise ValueError("only completed runs can be exported")
        recipe = self.repositories.recipes.as_domain(run.recipe_id)
        records = self.repositories.candidates.list(
            run_id,
            decision=CandidateDecision.accepted,
            limit=run.candidate_budget,
        )
        candidates = [candidate_from_record(record) for record in records]
        reports = {
            record.id: report
            for record in records
            if (report := self.repositories.candidates.get_quality_report(record.id)) is not None
        }
        resolved_export_id = export_id or uuid4().hex
        result = self.exports.create(
            export_id=resolved_export_id,
            run_id=run_id,
            candidates=candidates,
            quality_reports=reports,
            split_seed=recipe.random_seed,
            quality_threshold=recipe.quality_threshold,
            similarity_threshold=recipe.similarity_threshold,
            recipe_fingerprint=run.recipe_fingerprint,
            dataset_fingerprint=run.dataset_fingerprint,
            name=name,
            formats=formats,
            split_ratios=split_ratios,
        )
        record = self.repositories.exports.create(result.manifest, result.path)
        self.repositories.audit.record(
            event_type="export.created",
            entity_type="run",
            entity_id=run_id,
            payload={"export_id": record.id, "total_count": result.manifest.total_count},
        )
        return record

    def close(self) -> None:
        self.database.dispose()


@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container()


def clear_container_cache() -> None:
    if get_container.cache_info().currsize:
        get_container().close()
    get_container.cache_clear()
