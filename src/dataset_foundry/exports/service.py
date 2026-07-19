"""Atomic, immutable, fine-tuning-ready export snapshots."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from dataset_foundry.domain import (
    CandidateDecision,
    ExportFormat,
    ExportManifest,
    GeneratedCandidate,
    QualityReport,
)
from dataset_foundry.exports.formats import (
    alpaca_row,
    canonical_row,
    openai_chat_row,
    write_jsonl,
    write_parquet,
)
from dataset_foundry.exports.manifest import describe_artifact
from dataset_foundry.exports.splits import DEFAULT_SPLIT_RATIOS, SPLIT_ORDER, grouped_split

_SAFE_EXPORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ExportExistsError(FileExistsError):
    """Raised rather than replacing an already completed immutable snapshot."""


@dataclass(frozen=True, slots=True)
class ExportResult:
    path: Path
    manifest: ExportManifest


class ExportService:
    def __init__(self, artifact_root: str | Path) -> None:
        self.artifact_root = Path(artifact_root)

    def create(
        self,
        *,
        export_id: str,
        run_id: str,
        candidates: Sequence[GeneratedCandidate],
        quality_reports: Mapping[str, QualityReport] | None = None,
        split_seed: int = 42,
        quality_threshold: float = 0.72,
        similarity_threshold: float = 0.92,
        recipe_fingerprint: str | None = None,
        dataset_fingerprint: str | None = None,
        name: str = "Dataset export",
        formats: Sequence[ExportFormat] | None = None,
        split_ratios: Mapping[str, float] | None = None,
    ) -> ExportResult:
        if not _SAFE_EXPORT_ID.fullmatch(export_id):
            raise ValueError("export_id contains unsafe path characters")
        reports = dict(quality_reports or {})
        accepted = [
            candidate
            for candidate in candidates
            if candidate.id not in reports
            or reports[candidate.id].decision is CandidateDecision.accepted
        ]
        if not accepted:
            raise ValueError("an export requires at least one accepted candidate")
        accepted.sort(key=lambda candidate: (candidate.generation_index, candidate.id))
        selected_formats = tuple(dict.fromkeys(formats or list(ExportFormat)))
        if not selected_formats:
            raise ValueError("an export requires at least one format")
        if not name.strip():
            raise ValueError("export name must not be blank")
        configured_split_ratios = dict(split_ratios or DEFAULT_SPLIT_RATIOS)

        self.artifact_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = self.artifact_root / export_id
        if destination.exists():
            raise ExportExistsError(f"export {export_id} already exists")
        temporary = Path(tempfile.mkdtemp(prefix=f".{export_id}-", dir=self.artifact_root))
        temporary.chmod(0o700)
        try:
            assignment = grouped_split(
                accepted,
                seed=split_seed,
                ratios=configured_split_ratios,
            )
            artifacts = []

            if ExportFormat.canonical_jsonl in selected_formats:
                canonical_path = temporary / "canonical.jsonl"
                canonical_count = write_jsonl(
                    canonical_path,
                    (canonical_row(candidate, reports.get(candidate.id)) for candidate in accepted),
                )
                artifacts.append(
                    describe_artifact(
                        temporary,
                        canonical_path,
                        row_count=canonical_count,
                        format=ExportFormat.canonical_jsonl,
                    )
                )

            if ExportFormat.openai_chat_jsonl in selected_formats:
                openai_path = temporary / "openai-chat.jsonl"
                openai_count = write_jsonl(
                    openai_path, (openai_chat_row(candidate) for candidate in accepted)
                )
                artifacts.append(
                    describe_artifact(
                        temporary,
                        openai_path,
                        row_count=openai_count,
                        format=ExportFormat.openai_chat_jsonl,
                    )
                )

            if ExportFormat.alpaca_jsonl in selected_formats:
                alpaca_path = temporary / "alpaca.jsonl"
                alpaca_count = write_jsonl(
                    alpaca_path, (alpaca_row(candidate) for candidate in accepted)
                )
                artifacts.append(
                    describe_artifact(
                        temporary,
                        alpaca_path,
                        row_count=alpaca_count,
                        format=ExportFormat.alpaca_jsonl,
                    )
                )

            if ExportFormat.parquet in selected_formats:
                for split in SPLIT_ORDER:
                    split_candidates = [
                        candidate
                        for candidate in accepted
                        if assignment.by_candidate_id[candidate.id] == split
                    ]
                    path = temporary / f"{split}.parquet"
                    row_count = write_parquet(path, split_candidates, reports)
                    artifacts.append(
                        describe_artifact(
                            temporary,
                            path,
                            row_count=row_count,
                            format=ExportFormat.parquet,
                            split=split,
                        )
                    )

            card_path = temporary / "README.md"
            card_path.write_text(
                f"# {name.strip()}\n\n"
                f"- Run: `{run_id}`\n"
                f"- Accepted examples: {len(accepted)}\n"
                f"- Requested formats: {', '.join(item.value for item in selected_formats)}\n"
                f"- Split counts: train={assignment.counts['train']}, "
                f"validation={assignment.counts['validation']}, "
                f"test={assignment.counts['test']}\n"
                "- Generation and quality provenance: see `manifest.json`.\n\n"
                "This snapshot contains synthetic examples. Review licensing, privacy, and "
                "fitness for the target model before training.\n",
                encoding="utf-8",
            )
            card_path.chmod(0o600)
            artifacts.append(describe_artifact(temporary, card_path))

            first_trace = accepted[0].provider_trace
            manifest = ExportManifest(
                export_id=export_id,
                run_id=run_id,
                name=name.strip(),
                total_count=len(accepted),
                split_counts=assignment.counts,
                split_ratios=assignment.ratios,
                requested_split_ratios=configured_split_ratios,
                recipe_fingerprint=recipe_fingerprint,
                dataset_fingerprint=dataset_fingerprint,
                provider=first_trace.provider.value,
                model=first_trace.model,
                quality_threshold=quality_threshold,
                similarity_threshold=similarity_threshold,
                requested_formats=list(selected_formats),
                artifacts=artifacts,
            )
            manifest_path = temporary / "manifest.json"
            manifest_path.write_text(
                json.dumps(
                    manifest.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            manifest_path.chmod(0o600)
            os.replace(temporary, destination)
            return ExportResult(path=destination, manifest=manifest)
        except Exception:
            if temporary.exists():
                shutil.rmtree(temporary)
            raise
