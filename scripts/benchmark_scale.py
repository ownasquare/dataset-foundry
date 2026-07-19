"""Key-free generation, scoring, and export benchmark used by CI and local proof."""

from __future__ import annotations

import argparse
import asyncio
import json
import tempfile
import time
import tracemalloc
from pathlib import Path

from dataset_foundry.domain import (
    CandidateDecision,
    GenerationBatchRequest,
    GenerationRecipe,
)
from dataset_foundry.exports import ExportService
from dataset_foundry.ingestion import load_seed_dataset
from dataset_foundry.providers import OfflineProvider
from dataset_foundry.quality import QualityPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark the deterministic Dataset Foundry pipeline."
    )
    parser.add_argument("--count", type=int, default=2_000, choices=range(1, 10_001))
    parser.add_argument(
        "--seeds",
        type=Path,
        default=Path("examples/customer-support-seeds.jsonl"),
    )
    parser.add_argument("--quality-threshold", type=float, default=0.72)
    parser.add_argument("--similarity-threshold", type=float, default=0.96)
    return parser.parse_args()


async def benchmark(
    count: int,
    seed_path: Path,
    *,
    quality_threshold: float,
    similarity_threshold: float,
) -> dict[str, int | float | str]:
    if not 0 <= quality_threshold <= 1 or not 0 <= similarity_threshold <= 1:
        raise ValueError("quality and similarity thresholds must be between 0 and 1")
    loaded = load_seed_dataset(seed_path)
    batch_size = min(50, count)
    recipe = GenerationRecipe(
        name=f"benchmark-{count}",
        target_count=count,
        batch_size=batch_size,
        candidate_multiplier=1,
        quality_threshold=quality_threshold,
        similarity_threshold=similarity_threshold,
        random_seed=2_026,
        diversity_axes={
            "channel": ["email", "chat", "phone", "self-service"],
            "urgency": ["routine", "time-sensitive", "critical"],
        },
    )
    provider = OfflineProvider()
    candidates = []
    tracemalloc.start()
    started = time.perf_counter()
    for batch_index, offset in enumerate(range(0, count, batch_size)):
        request = GenerationBatchRequest(
            run_id="scale-benchmark",
            recipe=recipe,
            seed_examples=list(loaded.examples),
            batch_index=batch_index,
            requested_count=min(batch_size, count - offset),
        )
        candidates.extend((await provider.generate_batch(request)).candidates)

    reports = QualityPipeline(
        quality_threshold=recipe.quality_threshold,
        similarity_threshold=recipe.similarity_threshold,
    ).evaluate_many(candidates, seeds=loaded.examples, constraints=recipe.constraints)
    elapsed_seconds = time.perf_counter() - started
    _current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    report_by_id = {report.candidate_id: report for report in reports}
    accepted = sum(report.decision is CandidateDecision.accepted for report in reports)
    review = sum(report.decision is CandidateDecision.needs_review for report in reports)
    rejected = sum(report.decision is CandidateDecision.rejected for report in reports)
    if accepted == 0:
        raise RuntimeError("benchmark produced no accepted examples to export")

    with tempfile.TemporaryDirectory(prefix="dataset-foundry-benchmark-") as directory:
        export = ExportService(directory).create(
            export_id="benchmark-export",
            run_id="scale-benchmark",
            candidates=candidates,
            quality_reports=report_by_id,
            split_seed=recipe.random_seed,
            quality_threshold=recipe.quality_threshold,
            similarity_threshold=recipe.similarity_threshold,
            dataset_fingerprint=loaded.fingerprint,
        )
        artifact_count = len(export.manifest.artifacts)
        exported_count = export.manifest.total_count

    return {
        "mode": "offline-quality-kernel",
        "generated": len(candidates),
        "scored": len(reports),
        "accepted": accepted,
        "needs_review": review,
        "rejected": rejected,
        "exported": exported_count,
        "artifact_count": artifact_count,
        "elapsed_seconds": round(elapsed_seconds, 4),
        "examples_per_second": round(len(candidates) / max(elapsed_seconds, 1e-9), 2),
        "peak_memory_mib": round(peak_bytes / 1024 / 1024, 2),
        "quality_threshold": quality_threshold,
        "similarity_threshold": similarity_threshold,
        "seed_fingerprint": loaded.fingerprint,
    }


def main() -> None:
    args = parse_args()
    summary = asyncio.run(
        benchmark(
            args.count,
            args.seeds,
            quality_threshold=args.quality_threshold,
            similarity_threshold=args.similarity_threshold,
        )
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
