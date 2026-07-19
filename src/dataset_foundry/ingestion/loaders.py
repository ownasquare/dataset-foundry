"""Bounded seed-dataset loaders for JSON, JSONL, CSV, and Parquet."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import pyarrow.parquet as pq

from dataset_foundry.domain import TrainingExample
from dataset_foundry.ingestion.fingerprint import fingerprint_dataset, fingerprint_example
from dataset_foundry.ingestion.mapping import SeedMappingError, map_seed_row

SUPPORTED_EXTENSIONS = frozenset({".json", ".jsonl", ".csv", ".parquet"})
DEFAULT_MAX_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_ROWS = 50_000


class IngestionError(ValueError):
    """Raised for a bounded, user-correctable import failure."""


@dataclass(frozen=True, slots=True)
class LoadedDataset:
    source_path: Path
    examples: tuple[TrainingExample, ...]
    fingerprint: str
    size_bytes: int
    duplicate_count: int = 0

    @property
    def row_count(self) -> int:
        return len(self.examples)


def _read_json(path: Path) -> list[dict[str, Any]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IngestionError("JSON seed file is not valid UTF-8 JSON") from error
    if isinstance(value, dict) and isinstance(value.get("data"), list):
        value = value["data"]
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(row, dict) for row in value):
        raise IngestionError("JSON seed file must be an object, an array, or an object with data")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise IngestionError(f"JSONL row {line_number} must be an object")
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IngestionError("JSONL seed file contains invalid UTF-8 JSON") from error
    return rows


def _read_csv(path: Path) -> list[dict[str, Any]]:
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                raise IngestionError("CSV seed file requires a header row")
            return [dict(row) for row in reader]
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise IngestionError("CSV seed file could not be parsed") from error


def _read_parquet(path: Path, *, max_rows: int) -> list[dict[str, Any]]:
    try:
        parquet_file = pq.ParquetFile(path)
        if parquet_file.metadata.num_rows > max_rows:
            raise IngestionError(f"seed dataset exceeds the {max_rows:,}-row limit")
        return cast(list[dict[str, Any]], parquet_file.read().to_pylist())
    except IngestionError:
        raise
    except (OSError, ValueError) as error:
        raise IngestionError("Parquet seed file could not be parsed") from error


def load_seed_dataset(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> LoadedDataset:
    """Read, map, validate, and fingerprint one bounded local seed file."""

    source_path = Path(path)
    if not source_path.is_file():
        raise IngestionError("seed dataset path must be a regular file")
    extension = source_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise IngestionError(f"unsupported seed format; expected one of: {supported}")
    size_bytes = source_path.stat().st_size
    if size_bytes > max_bytes:
        raise IngestionError(f"seed file exceeds the {max_bytes:,}-byte limit")

    readers = {
        ".json": _read_json,
        ".jsonl": _read_jsonl,
        ".csv": _read_csv,
    }
    rows = (
        _read_parquet(source_path, max_rows=max_rows)
        if extension == ".parquet"
        else readers[extension](source_path)
    )
    if not rows:
        raise IngestionError("seed dataset must contain at least one row")
    if len(rows) > max_rows:
        raise IngestionError(f"seed dataset exceeds the {max_rows:,}-row limit")

    examples: list[TrainingExample] = []
    seen_fingerprints: set[str] = set()
    duplicate_count = 0
    for position, row in enumerate(rows):
        try:
            example = map_seed_row(row, position=position)
        except SeedMappingError as error:
            raise IngestionError(f"seed row {position + 1}: {error}") from error
        semantic_fingerprint = fingerprint_example(example)
        if semantic_fingerprint in seen_fingerprints:
            duplicate_count += 1
            continue
        seen_fingerprints.add(semantic_fingerprint)
        examples.append(example)
    return LoadedDataset(
        source_path=source_path,
        examples=tuple(examples),
        fingerprint=fingerprint_dataset(examples),
        size_bytes=size_bytes,
        duplicate_count=duplicate_count,
    )


def load_examples(
    path: str | Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_rows: int = DEFAULT_MAX_ROWS,
) -> list[TrainingExample]:
    """Convenience wrapper for callers that only need canonical rows."""

    return list(load_seed_dataset(path, max_bytes=max_bytes, max_rows=max_rows).examples)
