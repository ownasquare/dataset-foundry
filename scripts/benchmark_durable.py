"""Benchmark the complete SQLite queue, worker, quality, and export path."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import TypedDict

from dataset_foundry.config import Settings
from dataset_foundry.container import Container
from dataset_foundry.domain import ExportFormat, GenerationRecipe, ProviderName
from dataset_foundry.ingestion import load_seed_dataset


class DurableBenchmarkResult(TypedDict):
    mode: str
    target: int
    generated: int
    accepted: int
    needs_review: int
    rejected: int
    exported: int
    artifact_count: int
    elapsed_seconds: float
    generated_examples_per_second: float
    accepted_examples_per_second: float
    peak_memory_mib: float
    seed_fingerprint: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the complete deterministic Dataset Foundry workflow."
    )
    parser.add_argument("--count", type=int, default=250, choices=range(1, 5_001))
    parser.add_argument(
        "--seeds",
        type=Path,
        default=Path("examples/customer-support-seeds.jsonl"),
    )
    return parser.parse_args()


async def benchmark(count: int, seed_path: Path) -> DurableBenchmarkResult:
    loaded = load_seed_dataset(seed_path)
    with tempfile.TemporaryDirectory(prefix="dataset-foundry-durable-") as directory:
        root = Path(directory)
        settings = Settings(
            environment="test",
            data_dir=root,
            database_url=f"sqlite:///{root / 'benchmark.sqlite3'}",
            artifact_dir=root / "artifacts",
            default_provider="offline",
        )
        container = Container(settings)
        tracemalloc.start()
        started = time.perf_counter()
        try:
            project = container.repositories.projects.create(name="Durable scale benchmark")
            dataset = container.repositories.datasets.create(
                project_id=project.id,
                name="Benchmark seeds",
                fingerprint=loaded.fingerprint,
                examples=loaded.examples,
                source_filename=seed_path.name,
            )
            recipe = GenerationRecipe(
                name=f"durable-{count}",
                dataset_id=dataset.id,
                target_count=count,
                batch_size=min(50, count),
                candidate_multiplier=3,
                quality_threshold=0.72,
                similarity_threshold=0.96,
                random_seed=2_026,
                provider=ProviderName.offline,
                model="offline-deterministic-v1",
                diversity_axes={
                    "channel": ["email", "chat", "phone", "self-service"],
                    "urgency": ["routine", "time-sensitive", "critical"],
                },
            )
            stored_recipe = container.repositories.recipes.create(dataset.id, recipe)
            queued = container.generation.enqueue(
                dataset_id=dataset.id,
                recipe_id=stored_recipe.id,
            )
            worker_result = await container.worker(worker_id="durable-benchmark").run_once()
            if worker_result is None or worker_result.status != "completed":
                error_type = worker_result.error_type if worker_result else "missing_job"
                raise RuntimeError(f"durable benchmark failed: {error_type}")
            completed = container.repositories.runs.get(queued.id)
            exported = container.create_export(
                queued.id,
                name="Durable benchmark snapshot",
                formats=[ExportFormat.canonical_jsonl],
            )
            elapsed_seconds = time.perf_counter() - started
            _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
            return {
                "mode": "offline-durable-workflow",
                "target": count,
                "generated": completed.generated_count,
                "accepted": completed.accepted_count,
                "needs_review": completed.needs_review_count,
                "rejected": completed.rejected_count,
                "exported": exported.manifest_json["total_count"],
                "artifact_count": len(exported.manifest_json["artifacts"]),
                "elapsed_seconds": round(elapsed_seconds, 4),
                "generated_examples_per_second": round(
                    completed.generated_count / max(elapsed_seconds, 1e-9), 2
                ),
                "accepted_examples_per_second": round(
                    completed.accepted_count / max(elapsed_seconds, 1e-9), 2
                ),
                "peak_memory_mib": round(peak_bytes / 1024 / 1024, 2),
                "seed_fingerprint": loaded.fingerprint,
            }
        finally:
            tracemalloc.stop()
            container.close()


def main() -> None:
    args = parse_args()
    summary = asyncio.run(benchmark(args.count, args.seeds))
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
