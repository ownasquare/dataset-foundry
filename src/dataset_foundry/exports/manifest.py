"""Artifact hashing and manifest assembly helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

from dataset_foundry.domain import ExportArtifact, ExportFormat


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def describe_artifact(
    root: Path,
    path: Path,
    *,
    row_count: int | None = None,
    format: ExportFormat | None = None,
    split: str | None = None,
) -> ExportArtifact:
    return ExportArtifact(
        path=path.relative_to(root).as_posix(),
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
        row_count=row_count,
        format=format,
        split=split,
    )
