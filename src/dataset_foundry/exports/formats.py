"""Fine-tuning export row serializers and reloadable Parquet schema."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from dataset_foundry.domain import GeneratedCandidate, MessageRole, QualityReport
from dataset_foundry.ingestion.fingerprint import canonical_json

PARQUET_SCHEMA = pa.schema(
    [
        pa.field("id", pa.string(), nullable=False),
        pa.field(
            "messages",
            pa.list_(
                pa.struct(
                    [
                        pa.field("role", pa.string(), nullable=False),
                        pa.field("content", pa.string(), nullable=False),
                    ]
                )
            ),
            nullable=False,
        ),
        pa.field("metadata_json", pa.string(), nullable=False),
        pa.field("source_seed_ids", pa.list_(pa.string()), nullable=False),
        pa.field("provider", pa.string(), nullable=False),
        pa.field("model", pa.string(), nullable=False),
        pa.field("quality_score", pa.float64()),
    ]
)


def _messages(candidate: GeneratedCandidate) -> list[dict[str, str]]:
    return [
        {"role": message.role.value, "content": message.content} for message in candidate.messages
    ]


def canonical_row(
    candidate: GeneratedCandidate, report: QualityReport | None = None
) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "messages": _messages(candidate),
        "metadata": candidate.metadata,
        "source_seed_ids": candidate.source_seed_ids,
        "provider": candidate.provider_trace.provider.value,
        "model": candidate.provider_trace.model,
        "quality_score": report.score if report else None,
    }


def openai_chat_row(candidate: GeneratedCandidate) -> dict[str, Any]:
    return {"messages": _messages(candidate)}


def alpaca_row(candidate: GeneratedCandidate) -> dict[str, Any]:
    system = next(
        (message.content for message in candidate.messages if message.role is MessageRole.system),
        "",
    )
    instruction = next(
        message.content for message in candidate.messages if message.role is MessageRole.user
    )
    output = next(
        message.content for message in candidate.messages if message.role is MessageRole.assistant
    )
    row: dict[str, Any] = {"instruction": instruction, "input": "", "output": output}
    if system:
        row["system"] = system
    return row


def parquet_row(
    candidate: GeneratedCandidate, report: QualityReport | None = None
) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "messages": _messages(candidate),
        "metadata_json": canonical_json(candidate.metadata),
        "source_seed_ids": candidate.source_seed_ids,
        "provider": candidate.provider_trace.provider.value,
        "model": candidate.provider_trace.model,
        "quality_score": report.score if report else None,
    }


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(canonical_json(dict(row)))
            handle.write("\n")
            count += 1
    path.chmod(0o600)
    return count


def write_parquet(
    path: Path,
    candidates: Sequence[GeneratedCandidate],
    reports: Mapping[str, QualityReport],
) -> int:
    rows = [parquet_row(candidate, reports.get(candidate.id)) for candidate in candidates]
    table = pa.Table.from_pylist(rows, schema=PARQUET_SCHEMA)
    pq.write_table(table, path, compression="zstd")
    path.chmod(0o600)
    return len(rows)
