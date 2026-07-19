from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import pyarrow.parquet as pq
import pytest

from dataset_foundry.domain import (
    CandidateDecision,
    ChatMessage,
    ExportFormat,
    ExportManifest,
    GeneratedCandidate,
    ProviderName,
    ProviderTrace,
    QualityReport,
)
from dataset_foundry.exports import ExportExistsError, ExportService, grouped_split, sha256_file


def candidates() -> list[GeneratedCandidate]:
    generated = []
    for index in range(21):
        root = f"seed-{index // 2:02d}"
        generated.append(
            GeneratedCandidate(
                id=f"candidate-{index:02d}",
                messages=[
                    ChatMessage(
                        role="user",
                        content=f"Resolve support scenario {index} with a clear sequence of steps.",
                    ),
                    ChatMessage(
                        role="assistant",
                        content=(
                            f"Verify account context for scenario {index}, explain the documented "
                            "resolution, and provide a traceable escalation path when needed."
                        ),
                    ),
                ],
                metadata={"scenario": index},
                source_seed_ids=[root],
                generation_index=index,
                provider_trace=ProviderTrace(
                    provider=ProviderName.offline,
                    model="offline-deterministic-v1",
                    mode="offline-deterministic",
                ),
            )
        )
    return generated


def reports(values: list[GeneratedCandidate]) -> dict[str, QualityReport]:
    result = {
        candidate.id: QualityReport(
            candidate_id=candidate.id,
            score=0.85,
            automated_decision=CandidateDecision.accepted,
        )
        for candidate in values
    }
    rejected = values[-1]
    result[rejected.id] = QualityReport(
        candidate_id=rejected.id,
        score=0.2,
        automated_decision=CandidateDecision.rejected,
        reason_codes=["below_quality_threshold"],
        explanations=["Fixture rejection."],
    )
    return result


def test_export_formats_reload_hash_and_keep_lineage_groups_together(tmp_path: Path) -> None:
    generated = candidates()
    quality_reports = reports(generated)
    result = ExportService(tmp_path / "artifacts").create(
        export_id="export-1",
        run_id="run-1",
        candidates=generated,
        quality_reports=quality_reports,
        split_seed=17,
        recipe_fingerprint="b" * 64,
        dataset_fingerprint="c" * 64,
    )

    manifest_payload = json.loads((result.path / "manifest.json").read_text(encoding="utf-8"))
    manifest = ExportManifest.model_validate(manifest_payload)
    assert manifest.total_count == 20
    assert sum(manifest.split_counts.values()) == 20

    canonical_rows = [
        json.loads(line)
        for line in (result.path / "canonical.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    openai_rows = [
        json.loads(line)
        for line in (result.path / "openai-chat.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    alpaca_rows = [
        json.loads(line)
        for line in (result.path / "alpaca.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(canonical_rows) == len(openai_rows) == len(alpaca_rows) == 20
    assert set(openai_rows[0]) == {"messages"}
    assert {"instruction", "input", "output"} <= set(alpaca_rows[0])

    lineage_splits: dict[str, set[str]] = defaultdict(set)
    parquet_count = 0
    for split in ("train", "validation", "test"):
        rows = pq.read_table(result.path / f"{split}.parquet").to_pylist()
        parquet_count += len(rows)
        for row in rows:
            for root_seed_id in row["source_seed_ids"]:
                lineage_splits[root_seed_id].add(split)
    assert parquet_count == 20
    assert all(len(splits) == 1 for splits in lineage_splits.values())

    for artifact in manifest.artifacts:
        assert sha256_file(result.path / artifact.path) == artifact.sha256


def test_export_is_immutable_and_refuses_path_traversal(tmp_path: Path) -> None:
    generated = candidates()[:2]
    service = ExportService(tmp_path / "artifacts")
    service.create(export_id="fixed-export", run_id="run", candidates=generated)

    with pytest.raises(ExportExistsError):
        service.create(export_id="fixed-export", run_id="run", candidates=generated)
    with pytest.raises(ValueError, match="unsafe"):
        service.create(export_id="../escape", run_id="run", candidates=generated)


def test_export_honors_selected_format_name_and_split_contract(tmp_path: Path) -> None:
    result = ExportService(tmp_path / "artifacts").create(
        export_id="selected-export",
        run_id="run-selected",
        name="Alpaca handoff",
        candidates=candidates()[:10],
        formats=[ExportFormat.alpaca_jsonl],
        split_ratios={"train": 0.8, "validation": 0.1, "test": 0.1},
    )

    assert result.manifest.name == "Alpaca handoff"
    assert result.manifest.requested_formats == [ExportFormat.alpaca_jsonl]
    assert result.manifest.requested_split_ratios == {
        "train": 0.8,
        "validation": 0.1,
        "test": 0.1,
    }
    assert {artifact.path for artifact in result.manifest.artifacts} == {
        "alpaca.jsonl",
        "README.md",
    }
    assert (result.path / "alpaca.jsonl").is_file()
    assert not (result.path / "canonical.jsonl").exists()
    assert not (result.path / "train.parquet").exists()


def test_grouped_split_keeps_transitively_connected_lineage_in_one_split() -> None:
    base = candidates()[0]
    generated = [
        base.model_copy(update={"id": "candidate-ab", "source_seed_ids": ["seed-a", "seed-b"]}),
        base.model_copy(update={"id": "candidate-bc", "source_seed_ids": ["seed-b", "seed-c"]}),
        base.model_copy(update={"id": "candidate-cd", "source_seed_ids": ["seed-c", "seed-d"]}),
        base.model_copy(update={"id": "candidate-z", "source_seed_ids": ["seed-z"]}),
    ]

    assignment = grouped_split(
        generated,
        seed=41,
        ratios={"train": 0.5, "validation": 0.25, "test": 0.25},
    )

    connected_splits = {
        assignment.by_candidate_id[candidate_id]
        for candidate_id in ("candidate-ab", "candidate-bc", "candidate-cd")
    }
    assert len(connected_splits) == 1
