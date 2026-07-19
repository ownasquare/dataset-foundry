"""Stable, content-addressed fingerprints for seed and candidate data."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from typing import Any

from dataset_foundry.domain import ChatMessage, GeneratedCandidate, TrainingExample


def canonical_json(value: object) -> str:
    """Serialize a JSON-compatible value with a platform-stable representation."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _message_payload(messages: Iterable[ChatMessage]) -> list[dict[str, str]]:
    return [{"role": message.role.value, "content": message.content} for message in messages]


def canonical_example_payload(example: TrainingExample) -> dict[str, object]:
    """Return semantic example content, excluding transport-specific identifiers."""

    return {
        "messages": _message_payload(example.messages),
        "metadata": example.metadata,
    }


def canonical_candidate_payload(candidate: GeneratedCandidate) -> dict[str, object]:
    return {
        "messages": _message_payload(candidate.messages),
        "metadata": candidate.metadata,
    }


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fingerprint_example(example: TrainingExample) -> str:
    return sha256_text(canonical_json(canonical_example_payload(example)))


def fingerprint_candidate(candidate: GeneratedCandidate) -> str:
    return sha256_text(canonical_json(canonical_candidate_payload(candidate)))


def fingerprint_dataset(examples: Iterable[TrainingExample]) -> str:
    """Fingerprint dataset contents independent of import container and row order."""

    example_fingerprints = sorted(fingerprint_example(example) for example in examples)
    return sha256_text(canonical_json({"schema_version": "1", "examples": example_fingerprints}))


def fingerprint_mapping(mapping: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(mapping))
