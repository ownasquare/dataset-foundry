"""Dataset Foundry command-line product surface."""

from __future__ import annotations

import asyncio
import os
from importlib.resources import as_file, files
from typing import Annotated

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from dataset_foundry.api.app import create_app
from dataset_foundry.api.schemas import ProvidersView
from dataset_foundry.config import Settings
from dataset_foundry.container import Container
from dataset_foundry.domain import GenerationRecipe, RunStatus
from dataset_foundry.ingestion import load_seed_dataset

app = typer.Typer(
    name="dataset-foundry",
    help="Turn a small seed set into reviewable, fine-tuning-ready data.",
    no_args_is_help=True,
)
console = Console()


def _container() -> Container:
    return Container()


@app.command()
def serve(
    host: Annotated[str | None, typer.Option(help="Bind host override.")] = None,
    port: Annotated[int | None, typer.Option(help="Bind port override.")] = None,
) -> None:
    """Run the FastAPI service."""

    current = Settings()
    settings = Settings.model_validate(
        {
            **current.model_dump(),
            "host": host or current.host,
            "port": port or current.port,
        }
    )
    container = Container(settings)
    uvicorn.run(
        create_app(container),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


@app.command()
def worker(
    once: Annotated[bool, typer.Option(help="Process at most one queued job.")] = False,
    worker_id: Annotated[str | None, typer.Option(help="Lease-owner identifier.")] = None,
) -> None:
    """Run the durable generation worker."""

    container = _container()
    runtime = container.worker(worker_id=worker_id)
    if once:
        result = asyncio.run(runtime.run_once())
        if result is None:
            console.print("No queued jobs.")
        else:
            console.print(f"Job {result.job_id}: {result.status}")
        return
    try:
        asyncio.run(runtime.run_forever())
    except KeyboardInterrupt:
        console.print("Worker stopped.")


@app.command()
def doctor() -> None:
    """Check local database and provider readiness without exposing secrets."""

    container = _container()
    table = Table(title="Dataset Foundry readiness")
    table.add_column("Surface")
    table.add_column("Status")
    table.add_row("Database", "ready")
    table.add_row(
        "Data directory",
        "writable" if os.access(container.settings.data_dir, os.W_OK) else "not writable",
    )
    table.add_row(
        "Frontend assets",
        (
            "built"
            if (container.settings.frontend_dist / "index.html").is_file()
            else "not built (API only)"
        ),
    )
    status = ProvidersView.model_validate(container.providers.status())
    for provider in status.providers:
        table.add_row(
            f"Provider: {provider.id.value}",
            "configured" if provider.configured else "not configured",
        )
    console.print(table)


async def _process_until_terminal(container: Container, run_id: str) -> None:
    runtime = container.worker()
    for _ in range(1_000):
        run = container.repositories.runs.get(run_id)
        if run.status in {
            RunStatus.completed.value,
            RunStatus.failed.value,
            RunStatus.cancelled.value,
        }:
            if run.status != RunStatus.completed.value:
                raise RuntimeError(f"run ended with status {run.status}")
            return
        result = await runtime.run_once()
        if result is None:
            await asyncio.sleep(0.05)
    raise RuntimeError("run did not reach a terminal state within the worker bound")


@app.command()
def demo(
    target_count: Annotated[
        int,
        typer.Option(min=1, max=250, help="Number of accepted examples to create."),
    ] = 25,
) -> None:
    """Run an entirely offline seed-to-export demonstration."""

    container = _container()
    project = next(
        (
            record
            for record in container.repositories.projects.list(limit=10_000)
            if record.name == "Customer Support Demo"
        ),
        None,
    )
    if project is None:
        project = container.repositories.projects.create(
            name="Customer Support Demo",
            description="Versioned, network-free Dataset Foundry demonstration.",
            project_id="demo-project",
        )
    seed_resource = files("dataset_foundry.resources").joinpath("customer-support-seeds.jsonl")
    with as_file(seed_resource) as seed_path:
        loaded = load_seed_dataset(
            seed_path,
            max_bytes=container.settings.max_upload_bytes,
            max_rows=container.settings.max_seed_rows,
        )
        source_filename = seed_path.name
    dataset = container.repositories.datasets.create(
        project_id=project.id,
        name="Customer support seeds",
        fingerprint=loaded.fingerprint,
        examples=loaded.examples,
        source_filename=source_filename,
        metadata={"demo": True},
        dataset_id="demo-support-seeds",
    )
    recipe_id = f"demo-offline-{target_count}"
    try:
        recipe_record = container.repositories.recipes.get(recipe_id)
    except LookupError:
        recipe = GenerationRecipe(
            id=recipe_id,
            name="Offline support expansion",
            dataset_id=dataset.id,
            target_count=target_count,
            batch_size=min(20, target_count),
            candidate_multiplier=4,
            quality_threshold=0.72,
            similarity_threshold=0.92,
            random_seed=20260718,
            constraints=["Give a concrete next step", "Do not request passwords"],
            diversity_axes={
                "channel": ["email", "chat", "phone"],
                "urgency": ["routine", "time-sensitive"],
            },
        )
        recipe_record = container.repositories.recipes.create(dataset.id, recipe)

    completed_run = next(
        (
            record
            for record in container.repositories.runs.list(dataset_id=dataset.id, limit=10_000)
            if record.recipe_id == recipe_record.id
            and record.status == RunStatus.completed.value
            and container.repositories.exports.list(record.id)
        ),
        None,
    )
    if completed_run is not None:
        existing_export = container.repositories.exports.list(completed_run.id)[0]
        console.print(
            f"Offline demo already ready: {completed_run.accepted_count} accepted examples; "
            f"export {existing_export.id} at {existing_export.output_path}"
        )
        return

    run = container.generation.enqueue(dataset_id=dataset.id, recipe_id=recipe_record.id)
    try:
        asyncio.run(_process_until_terminal(container, run.id))
        export = container.create_export(run.id, export_id=f"demo-export-{target_count}")
    except RuntimeError as exc:
        console.print(f"Demo failed: {exc}")
        raise typer.Exit(code=1) from exc
    completed = container.repositories.runs.get(run.id)
    console.print(
        f"Offline demo complete: {completed.accepted_count} accepted examples; "
        f"export {export.id} at {export.output_path}"
    )


@app.command()
def generate(
    recipe_id: Annotated[str, typer.Option(help="Saved recipe ID.")],
    dataset_id: Annotated[str | None, typer.Option(help="Dataset override.")] = None,
    wait: Annotated[bool, typer.Option(help="Process locally until terminal.")] = False,
) -> None:
    """Queue a generation run from a saved recipe."""

    container = _container()
    recipe = container.repositories.recipes.as_domain(recipe_id)
    resolved_dataset = dataset_id or recipe.dataset_id
    if resolved_dataset is None:
        raise typer.BadParameter("the recipe is not bound to a dataset")
    run = container.generation.enqueue(dataset_id=resolved_dataset, recipe_id=recipe_id)
    if wait:
        asyncio.run(_process_until_terminal(container, run.id))
        run = container.repositories.runs.get(run.id)
    console.print(f"Run {run.id}: {run.status}")


@app.command(name="export")
def export_command(
    run_id: Annotated[str, typer.Option(help="Completed run ID.")],
) -> None:
    """Create an immutable multi-format export from an accepted run."""

    container = _container()
    record = container.create_export(run_id)
    console.print(f"Export {record.id}: {record.output_path}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
