from __future__ import annotations

import csv
import json
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dataset_foundry.ingestion import IngestionError, load_seed_dataset


def rows() -> list[dict[str, object]]:
    return [
        {
            "id": "one",
            "instruction": "Explain a late delivery.",
            "input": "Tracking stopped at the depot.",
            "output": "Confirm the address, check carrier status, and provide a revised window.",
            "metadata": {"category": "shipping"},
        },
        {
            "id": "two",
            "instruction": "Resolve a duplicate charge.",
            "input": "Two pending entries are visible.",
            "output": "Check whether one is an authorization and investigate if both charges post.",
            "metadata": {"category": "billing"},
        },
    ]


def write_formats(root: Path) -> list[Path]:
    source_rows = rows()
    json_path = root / "seeds.json"
    json_path.write_text(json.dumps(source_rows), encoding="utf-8")

    jsonl_path = root / "seeds.jsonl"
    jsonl_path.write_text("".join(json.dumps(row) + "\n" for row in source_rows), encoding="utf-8")

    csv_path = root / "seeds.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "instruction", "input", "output", "metadata"]
        )
        writer.writeheader()
        for row in source_rows:
            csv_row = dict(row)
            csv_row["metadata"] = json.dumps(row["metadata"])
            writer.writerow(csv_row)

    parquet_path = root / "seeds.parquet"
    pq.write_table(pa.Table.from_pylist(source_rows), parquet_path)
    return [json_path, jsonl_path, csv_path, parquet_path]


def write_duplicate_formats(root: Path) -> list[Path]:
    source_rows = rows()
    duplicate = dict(source_rows[0])
    duplicate["id"] = "duplicate-of-one"
    duplicate["instruction"] = f"  {duplicate['instruction']}  "
    duplicate["output"] = f"{duplicate['output']}  "
    source_rows.append(duplicate)

    jsonl_path = root / "duplicate-seeds.jsonl"
    jsonl_path.write_text(
        "".join(json.dumps(row) + "\n" for row in source_rows),
        encoding="utf-8",
    )

    csv_path = root / "duplicate-seeds.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["id", "instruction", "input", "output", "metadata"]
        )
        writer.writeheader()
        for row in source_rows:
            csv_row = dict(row)
            csv_row["metadata"] = json.dumps(row["metadata"])
            writer.writerow(csv_row)

    parquet_path = root / "duplicate-seeds.parquet"
    pq.write_table(pa.Table.from_pylist(source_rows), parquet_path)
    return [jsonl_path, csv_path, parquet_path]


def test_equivalent_formats_share_canonical_content_and_fingerprint(tmp_path: Path) -> None:
    loaded = [load_seed_dataset(path) for path in write_formats(tmp_path)]

    assert {dataset.fingerprint for dataset in loaded} == {loaded[0].fingerprint}
    expected_messages = [
        example.model_dump(mode="json", exclude={"id", "source_id", "root_seed_id"})
        for example in loaded[0].examples
    ]
    for dataset in loaded:
        assert dataset.row_count == 2
        actual_messages = [
            example.model_dump(mode="json", exclude={"id", "source_id", "root_seed_id"})
            for example in dataset.examples
        ]
        assert actual_messages == expected_messages


def test_duplicate_rows_are_removed_after_canonical_mapping_in_first_seen_order(
    tmp_path: Path,
) -> None:
    loaded = [load_seed_dataset(path) for path in write_duplicate_formats(tmp_path)]

    assert {dataset.fingerprint for dataset in loaded} == {loaded[0].fingerprint}
    for dataset in loaded:
        assert dataset.row_count == 2
        assert dataset.duplicate_count == 1
        assert [example.source_id for example in dataset.examples] == ["one", "two"]


def test_messages_shape_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "messages.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "chat-1",
                "messages": [
                    {"role": "system", "content": "Be clear."},
                    {"role": "user", "content": "Where is my order?"},
                    {"role": "assistant", "content": "Check the tracking page first."},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    loaded = load_seed_dataset(path)
    assert loaded.examples[0].system_prompt == "Be clear."


def test_prompt_completion_shape_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "completion.json"
    path.write_text(
        json.dumps({"prompt": "Summarize the request.", "completion": "A short summary."}),
        encoding="utf-8",
    )
    assert load_seed_dataset(path).examples[0].response == "A short summary."


def test_ingestion_rejects_unsupported_oversized_blank_and_too_many_rows(
    tmp_path: Path,
) -> None:
    unsupported = tmp_path / "seeds.txt"
    unsupported.write_text("hello", encoding="utf-8")
    with pytest.raises(IngestionError, match="unsupported"):
        load_seed_dataset(unsupported)

    valid = tmp_path / "valid.json"
    valid.write_text(json.dumps(rows()), encoding="utf-8")
    with pytest.raises(IngestionError, match="byte limit"):
        load_seed_dataset(valid, max_bytes=1)
    with pytest.raises(IngestionError, match="row limit"):
        load_seed_dataset(valid, max_rows=1)

    blank = tmp_path / "blank.jsonl"
    blank.write_text(
        json.dumps({"instruction": " ", "output": "answer"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(IngestionError, match="non-blank"):
        load_seed_dataset(blank)
