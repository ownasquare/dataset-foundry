"""Versioned Dataset Foundry HTTP workflow routes."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated, Any, TypeVar, cast

from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select

from dataset_foundry.api.errors import ApiProblem
from dataset_foundry.api.schemas import (
    ArtifactView,
    AuditEventView,
    CandidateCounts,
    CandidateView,
    DatasetView,
    ExportCreate,
    ExportView,
    OverviewView,
    Page,
    PreflightRequest,
    PreflightView,
    ProjectCreate,
    ProjectView,
    ProvidersView,
    RecipeCreate,
    RecipeView,
    ReviewCreate,
    ReviewView,
    RunCounts,
    RunCreate,
    RunView,
)
from dataset_foundry.container import Container
from dataset_foundry.domain import (
    CandidateDecision,
    ExportManifest,
    GenerationRecipe,
    ProviderTrace,
    QualityComponent,
    ReviewDecision,
    RunStatus,
    TrainingExample,
)
from dataset_foundry.generation.planner import build_preflight
from dataset_foundry.ingestion import SUPPORTED_EXTENSIONS, load_seed_dataset
from dataset_foundry.persistence.models import (
    CandidateRecord,
    DatasetRecord,
    ExportRecord,
    ProjectRecord,
    QualityReportRecord,
    RecipeRecord,
    ReviewRecord,
    RunRecord,
)

router = APIRouter(prefix="/api/v1")
R = TypeVar("R")


def _container(request: Request) -> Container:
    return cast(Container, request.app.state.container)


def _page(values: list[R], cursor: str | None, limit: int) -> Page[R]:
    start = 0
    if cursor is not None:
        for index, value in enumerate(values):
            if getattr(value, "id", None) == cursor:
                start = index + 1
                break
        else:
            raise ApiProblem(422, "Invalid cursor", "The pagination cursor is no longer valid.")
    items = values[start : start + limit]
    has_more = start + limit < len(values)
    next_cursor = getattr(items[-1], "id", None) if items and has_more else None
    return Page(items=items, next_cursor=next_cursor)


def _dataset_view(record: DatasetRecord, *, duplicate_count: int | None = None) -> DatasetView:
    suffix = Path(record.source_filename or "").suffix.lower().lstrip(".")
    persisted_duplicate_count = record.metadata_json.get("duplicate_count", 0)
    if not isinstance(persisted_duplicate_count, int) or persisted_duplicate_count < 0:
        persisted_duplicate_count = 0
    return DatasetView(
        id=record.id,
        project_id=record.project_id,
        name=record.name,
        source_format=suffix or "canonical",
        source_filename=record.source_filename,
        row_count=record.row_count,
        duplicate_count=(persisted_duplicate_count if duplicate_count is None else duplicate_count),
        fingerprint=record.fingerprint,
        created_at=record.created_at,
    )


def _project_view(container: Container, record: ProjectRecord) -> ProjectView:
    datasets = container.repositories.projects.list_datasets(record.id)
    dataset_ids = {dataset.id for dataset in datasets}
    runs = [
        run
        for run in container.repositories.runs.list(limit=10_000)
        if run.dataset_id in dataset_ids
    ]
    active = next(
        (run for run in runs if run.status in {RunStatus.queued.value, RunStatus.running.value}),
        None,
    )
    timestamps = [record.created_at]
    timestamps.extend(dataset.created_at for dataset in datasets)
    timestamps.extend(run.updated_at for run in runs)
    return ProjectView(
        id=record.id,
        name=record.name,
        description=record.description,
        created_at=record.created_at,
        seed_count=sum(dataset.row_count for dataset in datasets),
        generated_count=sum(run.generated_count for run in runs),
        accepted_count=sum(run.accepted_count for run in runs),
        last_activity=max(timestamps),
        active_run_id=active.id if active else None,
    )


def _recipe_view(container: Container, record: RecipeRecord) -> RecipeView:
    recipe = GenerationRecipe.model_validate(record.recipe_json)
    dataset = container.repositories.datasets.get(record.dataset_id)
    return RecipeView(
        id=record.id,
        project_id=dataset.project_id,
        dataset_id=record.dataset_id,
        name=recipe.name,
        task_description=recipe.task_description,
        target_count=recipe.target_count,
        batch_size=recipe.batch_size,
        candidate_multiplier=recipe.candidate_multiplier,
        min_quality_score=recipe.quality_threshold,
        max_similarity=recipe.similarity_threshold,
        seed=recipe.random_seed,
        language=recipe.language,
        constraints=recipe.constraints,
        diversity_axes=recipe.diversity_axes,
        provider=recipe.provider,
        model=recipe.model,
        allow_external_data_transfer=recipe.allow_external_data_transfer,
        created_at=record.created_at,
    )


def _run_view(container: Container, record: RunRecord) -> RunView:
    dataset = container.repositories.datasets.get(record.dataset_id)
    project = container.repositories.projects.get(dataset.project_id)
    recipe = container.repositories.recipes.as_domain(record.recipe_id)
    candidates = container.repositories.candidates.list(
        record.id,
        limit=record.candidate_budget,
    )
    scores = [
        candidate.quality_score for candidate in candidates if candidate.quality_score is not None
    ]
    duplicate_count = 0
    if candidates:
        candidate_ids = [candidate.id for candidate in candidates]
        with container.database.session() as session:
            reports = session.scalars(
                select(QualityReportRecord).where(
                    QualityReportRecord.candidate_id.in_(candidate_ids)
                )
            )
            duplicate_count = sum(
                bool({"exact_duplicate", "near_duplicate"} & set(report.reason_codes_json))
                for report in reports
            )
    return RunView(
        id=record.id,
        project_id=dataset.project_id,
        project_name=project.name,
        dataset_id=record.dataset_id,
        recipe_id=record.recipe_id,
        name=recipe.name,
        provider=recipe.provider,
        model=recipe.model,
        status=record.status,
        target_count=record.target_count,
        candidate_budget=record.candidate_budget,
        generated_count=record.generated_count,
        accepted_count=record.accepted_count,
        rejected_count=record.rejected_count,
        needs_review_count=record.needs_review_count,
        progress=min(1.0, record.accepted_count / record.target_count),
        average_quality=sum(scores) / len(scores) if scores else None,
        duplicate_rate=duplicate_count / len(candidates) if candidates else 0,
        error_type=record.error_type,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _candidate_view(
    record: CandidateRecord,
    report: QualityReportRecord | None = None,
    review: ReviewRecord | None = None,
    source_examples: list[TrainingExample] | None = None,
) -> CandidateView:
    trace = ProviderTrace.model_validate(record.provider_trace_json)
    effective = record.final_decision or record.automated_decision
    example = TrainingExample(
        id=record.id,
        messages=record.messages_json,
        metadata=record.metadata_json,
        source_id=record.id,
        root_seed_id=record.source_seed_ids_json[0] if record.source_seed_ids_json else None,
    )
    return CandidateView(
        id=record.id,
        run_id=record.run_id,
        example=example,
        automated_decision=(
            CandidateDecision(record.automated_decision) if record.automated_decision else None
        ),
        effective_decision=CandidateDecision(effective) if effective else None,
        quality_score=record.quality_score,
        reason_codes=report.reason_codes_json if report else [],
        components=(
            [QualityComponent.model_validate(component) for component in report.components_json]
            if report
            else []
        ),
        explanations=report.explanations_json if report else [],
        nearest_match_id=report.nearest_match_id if report else None,
        nearest_similarity=report.nearest_similarity if report else None,
        reviewer_note=review.note if review else None,
        source_seed_ids=record.source_seed_ids_json,
        source_examples=source_examples or [],
        generation_index=record.generation_index,
        provider=trace.provider,
        model=trace.model,
        created_at=record.created_at,
    )


def _export_view(record: ExportRecord) -> ExportView:
    manifest = ExportManifest.model_validate(record.manifest_json)
    artifacts = [
        ArtifactView(
            filename=artifact.path,
            format=artifact.format,
            split=artifact.split,
            row_count=artifact.row_count,
            size_bytes=artifact.size_bytes,
            sha256=artifact.sha256,
            download_url=f"/api/v1/exports/{record.id}/download/{artifact.path}",
        )
        for artifact in manifest.artifacts
    ]
    return ExportView(
        id=record.id,
        run_id=record.run_id,
        status="ready" if record.status == "completed" else record.status,
        manifest=manifest,
        artifacts=artifacts,
        created_at=record.created_at,
    )


@router.get("/overview", response_model=OverviewView)
def overview(request: Request) -> OverviewView:
    container = _container(request)
    projects = container.repositories.projects.list(limit=10_000)
    datasets = container.repositories.datasets.list(limit=10_000)
    runs = container.repositories.runs.list(limit=10_000)
    run_counts = RunCounts()
    candidate_counts = CandidateCounts()
    export_count = 0
    for run in runs:
        setattr(run_counts, run.status, getattr(run_counts, run.status) + 1)
        candidate_counts.accepted += run.accepted_count
        candidate_counts.needs_review += run.needs_review_count
        candidate_counts.rejected += run.rejected_count
        export_count += len(container.repositories.exports.list(run.id))
    return OverviewView(
        projects=len(projects),
        datasets=len(datasets),
        seed_examples=sum(dataset.row_count for dataset in datasets),
        generated_examples=sum(run.generated_count for run in runs),
        runs=run_counts,
        candidates=candidate_counts,
        exports=export_count,
    )


@router.post("/projects", status_code=201, response_model=ProjectView)
def create_project(payload: ProjectCreate, request: Request) -> ProjectView:
    container = _container(request)
    record = container.repositories.projects.create(
        name=payload.name,
        description=payload.description,
    )
    return _project_view(container, record)


@router.get("/projects", response_model=Page[ProjectView])
def list_projects(
    request: Request,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ProjectView]:
    container = _container(request)
    values = [
        _project_view(container, record)
        for record in container.repositories.projects.list(limit=10_000)
    ]
    return _page(values, cursor, limit)


@router.post("/projects/{project_id}/seeds", status_code=201, response_model=DatasetView)
async def upload_seeds(
    project_id: str,
    request: Request,
    file: Annotated[UploadFile, File()],
    dataset_name: Annotated[str | None, Form()] = None,
) -> DatasetView:
    container = _container(request)
    container.repositories.projects.get(project_id)
    filename = Path(file.filename or "seeds.jsonl").name
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ApiProblem(422, "Unsupported seed format", "Use JSON, JSONL, CSV, or Parquet.")
    content = await file.read(container.settings.max_upload_bytes + 1)
    await file.close()
    if len(content) > container.settings.max_upload_bytes:
        raise ApiProblem(413, "Upload too large", "The seed file exceeds the upload limit.")
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
            handle.write(content)
            temporary_path = Path(handle.name)
        loaded = load_seed_dataset(
            temporary_path,
            max_bytes=container.settings.max_upload_bytes,
            max_rows=container.settings.max_seed_rows,
        )
        record = container.repositories.datasets.create(
            project_id=project_id,
            name=(dataset_name or Path(filename).stem or "Seed dataset"),
            fingerprint=loaded.fingerprint,
            examples=loaded.examples,
            source_filename=filename,
            metadata={
                "source_format": suffix.lstrip("."),
                "duplicate_count": loaded.duplicate_count,
            },
        )
        return _dataset_view(record, duplicate_count=loaded.duplicate_count)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


@router.get("/projects/{project_id}/datasets", response_model=Page[DatasetView])
def list_datasets(
    project_id: str,
    request: Request,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[DatasetView]:
    container = _container(request)
    container.repositories.projects.get(project_id)
    values = [
        _dataset_view(record)
        for record in container.repositories.datasets.list(
            project_id=project_id,
            limit=10_000,
        )
    ]
    return _page(values, cursor, limit)


@router.post("/projects/{project_id}/recipes", status_code=201, response_model=RecipeView)
def create_recipe(
    project_id: str,
    payload: RecipeCreate,
    request: Request,
) -> RecipeView:
    container = _container(request)
    project = container.repositories.projects.get(project_id)
    datasets = container.repositories.projects.list_datasets(project.id)
    dataset_id = payload.dataset_id or (datasets[0].id if datasets else None)
    if dataset_id is None:
        raise ApiProblem(422, "Seed dataset required", "Import seed data before creating a recipe.")
    dataset = container.repositories.datasets.get(dataset_id)
    if dataset.project_id != project_id:
        raise ApiProblem(422, "Dataset mismatch", "The dataset does not belong to this project.")
    try:
        recipe = GenerationRecipe(
            name=payload.name,
            dataset_id=dataset_id,
            task_description=payload.task_description,
            target_count=payload.target_count,
            batch_size=payload.batch_size,
            candidate_multiplier=payload.candidate_multiplier,
            quality_threshold=payload.min_quality_score,
            similarity_threshold=payload.max_similarity,
            provider=payload.provider,
            model=payload.model,
            random_seed=payload.seed,
            language=payload.language,
            constraints=payload.constraints,
            diversity_axes=payload.diversity_axes,
            allow_external_data_transfer=payload.allow_external_data_transfer,
        )
    except ValueError as exc:
        raise ApiProblem(422, "Invalid recipe", str(exc)) from exc
    record = container.repositories.recipes.create(dataset_id, recipe)
    return _recipe_view(container, record)


@router.get("/projects/{project_id}/recipes", response_model=Page[RecipeView])
def list_recipes(
    project_id: str,
    request: Request,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[RecipeView]:
    container = _container(request)
    dataset_ids = {
        record.id for record in container.repositories.projects.list_datasets(project_id)
    }
    values = [
        _recipe_view(container, record)
        for record in container.repositories.recipes.list()
        if record.dataset_id in dataset_ids
    ]
    return _page(values, cursor, limit)


@router.post("/recipes/{recipe_id}/preflight", response_model=PreflightView)
def preflight(recipe_id: str, payload: PreflightRequest, request: Request) -> PreflightView:
    container = _container(request)
    stored = container.repositories.recipes.as_domain(recipe_id)
    dataset_id = payload.dataset_id or stored.dataset_id
    if dataset_id is None:
        raise ApiProblem(422, "Dataset required", "The recipe is not bound to a dataset.")
    if dataset_id != stored.dataset_id:
        raise ApiProblem(422, "Dataset mismatch", "Preflight dataset must match the recipe.")
    updates: dict[str, Any] = {}
    if payload.provider is not None:
        updates["provider"] = payload.provider
    if payload.model is not None:
        updates["model"] = payload.model
    if payload.allow_external_data_transfer is not None:
        updates["allow_external_data_transfer"] = payload.allow_external_data_transfer
    try:
        recipe = GenerationRecipe.model_validate({**stored.model_dump(), **updates})
    except ValueError as exc:
        raise ApiProblem(422, "Invalid preflight configuration", str(exc)) from exc
    seeds = container.repositories.datasets.list_examples(dataset_id)
    result = build_preflight(
        recipe,
        seeds,
        provider_configured=container.settings.provider_configured(recipe.provider.value),
    )
    return PreflightView.model_validate({**result.model_dump(), "seed_count": len(seeds)})


@router.post("/runs", status_code=202, response_model=RunView)
def create_run(payload: RunCreate, request: Request) -> RunView:
    container = _container(request)
    recipe = container.repositories.recipes.as_domain(payload.recipe_id)
    dataset_id = payload.dataset_id or recipe.dataset_id
    if dataset_id is None or dataset_id != recipe.dataset_id:
        raise ApiProblem(422, "Dataset mismatch", "The run dataset must match the recipe.")
    dataset = container.repositories.datasets.get(dataset_id)
    if payload.project_id is not None and payload.project_id != dataset.project_id:
        raise ApiProblem(422, "Project mismatch", "The dataset does not belong to this project.")
    if payload.provider is not None and payload.provider != recipe.provider:
        raise ApiProblem(422, "Provider mismatch", "Save provider changes in a new recipe first.")
    if payload.model is not None and payload.model != recipe.model:
        raise ApiProblem(422, "Model mismatch", "Save model changes in a new recipe first.")
    if (
        payload.allow_external_data_transfer is not None
        and payload.allow_external_data_transfer != recipe.allow_external_data_transfer
    ):
        raise ApiProblem(422, "Consent mismatch", "Save consent changes in a new recipe first.")
    if not container.settings.provider_configured(recipe.provider.value):
        raise ApiProblem(
            422,
            "Provider not configured",
            f"{recipe.provider.value} is not configured.",
        )
    run = container.generation.enqueue(dataset_id=dataset_id, recipe_id=payload.recipe_id)
    return _run_view(container, run)


@router.get("/runs", response_model=Page[RunView])
def list_runs(
    request: Request,
    dataset_id: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[RunView]:
    container = _container(request)
    values = [
        _run_view(container, record)
        for record in container.repositories.runs.list(dataset_id=dataset_id, limit=10_000)
    ]
    return _page(values, cursor, limit)


@router.get("/runs/{run_id}", response_model=RunView)
def get_run(run_id: str, request: Request) -> RunView:
    container = _container(request)
    return _run_view(container, container.repositories.runs.get(run_id))


@router.post("/runs/{run_id}/cancel", response_model=RunView)
def cancel_run(run_id: str, request: Request) -> RunView:
    container = _container(request)
    record = container.repositories.runs.get(run_id)
    if record.status not in {RunStatus.queued.value, RunStatus.running.value}:
        raise ApiProblem(409, "Run is terminal", "Only queued or running runs can be cancelled.")
    cancelled = container.repositories.runs.transition(run_id, RunStatus.cancelled)
    container.repositories.audit.record(
        event_type="run.cancelled",
        entity_type="run",
        entity_id=run_id,
    )
    return _run_view(container, cancelled)


@router.get("/runs/{run_id}/events", response_model=Page[AuditEventView])
def run_events(
    run_id: str,
    request: Request,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[AuditEventView]:
    container = _container(request)
    container.repositories.runs.get(run_id)
    values = [
        AuditEventView(
            id=record.id,
            event_type=record.event_type,
            entity_type=record.entity_type,
            entity_id=record.entity_id,
            actor=record.actor,
            payload=record.payload_json,
            created_at=record.created_at,
        )
        for record in container.repositories.audit.list(entity_id=run_id, limit=10_000)
    ]
    return _page(values, cursor, limit)


@router.get("/runs/{run_id}/candidates", response_model=Page[CandidateView])
def list_candidates(
    run_id: str,
    request: Request,
    decision: CandidateDecision | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[CandidateView]:
    container = _container(request)
    run = container.repositories.runs.get(run_id)
    after_generation_index: int | None = None
    after_id: str | None = None
    if cursor is not None:
        cursor_record = container.repositories.candidates.get(cursor)
        if cursor_record.run_id != run_id:
            raise ApiProblem(422, "Invalid cursor", "The cursor belongs to a different run.")
        after_generation_index = cursor_record.generation_index
        after_id = cursor_record.id
    records = container.repositories.candidates.list(
        run_id,
        decision=decision,
        limit=limit + 1,
        after_generation_index=after_generation_index,
        after_id=after_id,
    )
    has_more = len(records) > limit
    records = records[:limit]
    reports: dict[str, QualityReportRecord] = {}
    reviews: dict[str, ReviewRecord] = {}
    source_examples: dict[str, TrainingExample] = {}
    if records:
        source_examples = container.repositories.datasets.get_examples(
            run.dataset_id,
            {source_id for record in records for source_id in record.source_seed_ids_json},
        )
        with container.database.session() as session:
            reports = {
                report.candidate_id: report
                for report in session.scalars(
                    select(QualityReportRecord).where(
                        QualityReportRecord.candidate_id.in_([record.id for record in records])
                    )
                )
            }
            for review in session.scalars(
                select(ReviewRecord)
                .where(ReviewRecord.candidate_id.in_([record.id for record in records]))
                .order_by(ReviewRecord.created_at, ReviewRecord.id)
            ):
                reviews[review.candidate_id] = review
    items = [
        _candidate_view(
            record,
            reports.get(record.id),
            reviews.get(record.id),
            [
                source_examples[source_id]
                for source_id in record.source_seed_ids_json
                if source_id in source_examples
            ],
        )
        for record in records
    ]
    return Page(
        items=items,
        next_cursor=items[-1].id if items and has_more else None,
    )


@router.post("/candidates/{candidate_id}/reviews", status_code=201, response_model=ReviewView)
def review_candidate(
    candidate_id: str,
    payload: ReviewCreate,
    request: Request,
) -> ReviewView:
    container = _container(request)
    review = container.repositories.reviews.record(
        ReviewDecision(
            candidate_id=candidate_id,
            decision=payload.decision,
            note=payload.note,
            reviewer=payload.reviewer,
        )
    )
    return _review_view(review)


def _review_view(record: ReviewRecord) -> ReviewView:
    return ReviewView(
        id=record.id,
        candidate_id=record.candidate_id,
        decision=CandidateDecision(record.decision),
        note=record.note,
        reviewer=record.reviewer,
        created_at=record.created_at,
    )


@router.post("/runs/{run_id}/exports", status_code=201, response_model=ExportView)
def create_export(
    run_id: str,
    payload: ExportCreate,
    request: Request,
) -> ExportView:
    container = _container(request)
    run = container.repositories.runs.get(run_id)
    if run.status != RunStatus.completed.value:
        raise ApiProblem(409, "Run is not complete", "Complete the run before exporting it.")
    try:
        record = container.create_export(
            run_id,
            name=payload.name,
            formats=payload.formats,
            split_ratios={
                "train": payload.train_percent / 100,
                "validation": payload.validation_percent / 100,
                "test": payload.test_percent / 100,
            },
        )
    except ValueError as exc:
        raise ApiProblem(422, "Export unavailable", str(exc)) from exc
    return _export_view(record)


@router.get("/exports", response_model=Page[ExportView])
def list_exports(
    request: Request,
    run_id: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Page[ExportView]:
    container = _container(request)
    run_ids = (
        [run_id] if run_id else [run.id for run in container.repositories.runs.list(limit=10_000)]
    )
    records = [
        record for current in run_ids for record in container.repositories.exports.list(current)
    ]
    records.sort(key=lambda record: (record.created_at, record.id), reverse=True)
    values = [_export_view(record) for record in records]
    return _page(values, cursor, limit)


@router.get("/exports/{export_id}", response_model=ExportView)
def get_export(export_id: str, request: Request) -> ExportView:
    return _export_view(_container(request).repositories.exports.get(export_id))


@router.get("/exports/{export_id}/download/{filename:path}")
def download_export(export_id: str, filename: str, request: Request) -> FileResponse:
    record = _container(request).repositories.exports.get(export_id)
    root = Path(record.output_path).resolve()
    artifact = (root / filename).resolve()
    if not artifact.is_relative_to(root) or not artifact.is_file():
        raise ApiProblem(404, "Artifact not found", "The requested export artifact does not exist.")
    return FileResponse(artifact, filename=artifact.name)


@router.get("/providers", response_model=ProvidersView)
def provider_status(request: Request) -> ProvidersView:
    return ProvidersView.model_validate(_container(request).providers.status())
